#![cfg_attr(not(target_os = "windows"), allow(dead_code))]

#[cfg(target_os = "windows")]
mod windows_drop {
    use std::collections::{HashMap, VecDeque};
    use std::ffi::c_void;
    use std::ptr;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::{Mutex, OnceLock};

    type Hwnd = isize;
    type Hresult = i32;
    type Dword = u32;
    type Ulong = u32;

    const S_OK: Hresult = 0;
    const S_FALSE: Hresult = 1;
    const E_NOINTERFACE: Hresult = -2147467262;
    const E_POINTER: Hresult = -2147467261;
    const DROPEFFECT_NONE: Dword = 0;
    const DROPEFFECT_COPY: Dword = 1;
    const CF_HDROP: u16 = 15;
    const DVASPECT_CONTENT: Dword = 1;
    const TYMED_HGLOBAL: Dword = 1;

    #[repr(C)]
    #[derive(Clone, Copy)]
    struct Guid {
        data1: u32,
        data2: u16,
        data3: u16,
        data4: [u8; 8],
    }

    const IID_IUNKNOWN: Guid = Guid {
        data1: 0,
        data2: 0,
        data3: 0,
        data4: [0xc0, 0, 0, 0, 0, 0, 0, 0x46],
    };
    const IID_IDROPTARGET: Guid = Guid {
        data1: 0x00000122,
        data2: 0,
        data3: 0,
        data4: [0xc0, 0, 0, 0, 0, 0, 0, 0x46],
    };

    #[repr(C)]
    struct FormatEtc {
        cf_format: u16,
        ptd: *mut c_void,
        dw_aspect: Dword,
        lindex: i32,
        tymed: Dword,
    }

    #[repr(C)]
    struct StgMedium {
        tymed: Dword,
        handle: isize,
        release_unknown: *mut c_void,
    }

    #[repr(C)]
    struct PointL {
        x: i32,
        y: i32,
    }

    #[repr(C)]
    struct DataObjectVTable {
        query_interface: usize,
        add_ref: usize,
        release: usize,
        get_data: unsafe extern "system" fn(*mut IDataObject, *mut FormatEtc, *mut StgMedium) -> Hresult,
    }

    #[repr(C)]
    struct IDataObject {
        vtable: *const DataObjectVTable,
    }

    #[repr(C)]
    struct DropTargetVTable {
        query_interface:
            unsafe extern "system" fn(*mut DropTarget, *const Guid, *mut *mut c_void) -> Hresult,
        add_ref: unsafe extern "system" fn(*mut DropTarget) -> Ulong,
        release: unsafe extern "system" fn(*mut DropTarget) -> Ulong,
        drag_enter: unsafe extern "system" fn(*mut DropTarget, *mut IDataObject, Dword, PointL, *mut Dword) -> Hresult,
        drag_over: unsafe extern "system" fn(*mut DropTarget, Dword, PointL, *mut Dword) -> Hresult,
        drag_leave: unsafe extern "system" fn(*mut DropTarget) -> Hresult,
        drop: unsafe extern "system" fn(*mut DropTarget, *mut IDataObject, Dword, PointL, *mut Dword) -> Hresult,
    }

    #[repr(C)]
    struct DropTarget {
        vtable: *const DropTargetVTable,
        refs: AtomicU32,
    }

    struct State {
        registered: HashMap<Hwnd, usize>,
        queue: VecDeque<Vec<u16>>,
        ole_initialized: bool,
    }

    static STATE: OnceLock<Mutex<State>> = OnceLock::new();

    fn state() -> &'static Mutex<State> {
        STATE.get_or_init(|| Mutex::new(State {
            registered: HashMap::new(),
            queue: VecDeque::new(),
            ole_initialized: false,
        }))
    }

    fn guid_equals(left: *const Guid, right: &Guid) -> bool {
        if left.is_null() {
            return false;
        }
        unsafe {
            (*left).data1 == right.data1
                && (*left).data2 == right.data2
                && (*left).data3 == right.data3
                && (*left).data4 == right.data4
        }
    }

    unsafe extern "system" fn query_interface(
        this: *mut DropTarget,
        iid: *const Guid,
        out: *mut *mut c_void,
    ) -> Hresult {
        if out.is_null() {
            return E_POINTER;
        }
        if guid_equals(iid, &IID_IUNKNOWN) || guid_equals(iid, &IID_IDROPTARGET) {
            *out = this.cast();
            add_ref(this);
            S_OK
        } else {
            *out = ptr::null_mut();
            E_NOINTERFACE
        }
    }

    unsafe extern "system" fn add_ref(this: *mut DropTarget) -> Ulong {
        (*this).refs.fetch_add(1, Ordering::Relaxed) + 1
    }

    unsafe extern "system" fn release(this: *mut DropTarget) -> Ulong {
        let remaining = (*this).refs.fetch_sub(1, Ordering::Release) - 1;
        if remaining == 0 {
            std::sync::atomic::fence(Ordering::Acquire);
            drop(Box::from_raw(this));
        }
        remaining
    }

    unsafe fn set_effect(effect: *mut Dword, value: Dword) {
        if !effect.is_null() {
            *effect = value;
        }
    }

    unsafe extern "system" fn drag_enter(
        _this: *mut DropTarget,
        _data: *mut IDataObject,
        _keys: Dword,
        _point: PointL,
        effect: *mut Dword,
    ) -> Hresult {
        set_effect(effect, DROPEFFECT_COPY);
        S_OK
    }

    unsafe extern "system" fn drag_over(
        _this: *mut DropTarget,
        _keys: Dword,
        _point: PointL,
        effect: *mut Dword,
    ) -> Hresult {
        set_effect(effect, DROPEFFECT_COPY);
        S_OK
    }

    unsafe extern "system" fn drag_leave(_this: *mut DropTarget) -> Hresult {
        S_OK
    }

    unsafe extern "system" fn drop_data(
        _this: *mut DropTarget,
        data: *mut IDataObject,
        _keys: Dword,
        _point: PointL,
        effect: *mut Dword,
    ) -> Hresult {
        if data.is_null() {
            set_effect(effect, DROPEFFECT_NONE);
            return S_OK;
        }
        let mut format = FormatEtc {
            cf_format: CF_HDROP,
            ptd: ptr::null_mut(),
            dw_aspect: DVASPECT_CONTENT,
            lindex: -1,
            tymed: TYMED_HGLOBAL,
        };
        let mut medium = StgMedium {
            tymed: 0,
            handle: 0,
            release_unknown: ptr::null_mut(),
        };
        let get_data = (*(*data).vtable).get_data;
        if get_data(data, &mut format, &mut medium) < 0 {
            set_effect(effect, DROPEFFECT_NONE);
            return S_OK;
        }
        let mut paths = Vec::new();
        let count = DragQueryFileW(medium.handle, u32::MAX, ptr::null_mut(), 0);
        for index in 0..count {
            let length = DragQueryFileW(medium.handle, index, ptr::null_mut(), 0);
            if length == 0 {
                continue;
            }
            let mut chars = vec![0_u16; length as usize + 1];
            if DragQueryFileW(medium.handle, index, chars.as_mut_ptr(), chars.len() as u32) > 0 {
                paths.push(String::from_utf16_lossy(&chars[..length as usize]));
            }
        }
        ReleaseStgMedium(&mut medium);
        if !paths.is_empty() {
            let mut payload = Vec::new();
            for path in paths {
                payload.extend(path.encode_utf16());
                payload.push(0);
            }
            payload.push(0);
            if let Ok(mut guard) = state().lock() {
                guard.queue.push_back(payload);
            }
            set_effect(effect, DROPEFFECT_COPY);
        } else {
            set_effect(effect, DROPEFFECT_NONE);
        }
        S_OK
    }

    static VTABLE: DropTargetVTable = DropTargetVTable {
        query_interface,
        add_ref,
        release,
        drag_enter,
        drag_over,
        drag_leave,
        drop: drop_data,
    };

    #[link(name = "ole32")]
    extern "system" {
        fn OleInitialize(reserved: *mut c_void) -> Hresult;
        fn OleUninitialize();
        fn RegisterDragDrop(hwnd: Hwnd, drop_target: *mut DropTarget) -> Hresult;
        fn RevokeDragDrop(hwnd: Hwnd) -> Hresult;
        fn ReleaseStgMedium(medium: *mut StgMedium);
    }

    #[link(name = "shell32")]
    extern "system" {
        fn DragQueryFileW(drop: isize, index: u32, buffer: *mut u16, count: u32) -> u32;
    }

    #[no_mangle]
    pub extern "system" fn syp_drop_initialize() -> i32 {
        let mut guard = match state().lock() {
            Ok(value) => value,
            Err(_) => return -1,
        };
        if guard.ole_initialized {
            return 1;
        }
        let result = unsafe { OleInitialize(ptr::null_mut()) };
        if result == S_OK || result == S_FALSE {
            guard.ole_initialized = true;
            1
        } else {
            result
        }
    }

    #[no_mangle]
    pub extern "system" fn syp_drop_register(hwnd: Hwnd) -> i32 {
        if hwnd == 0 {
            return 0;
        }
        if syp_drop_initialize() <= 0 {
            return 0;
        }
        let mut guard = match state().lock() {
            Ok(value) => value,
            Err(_) => return 0,
        };
        if guard.registered.contains_key(&hwnd) {
            return 1;
        }
        let target = Box::into_raw(Box::new(DropTarget {
            vtable: &VTABLE,
            refs: AtomicU32::new(1),
        }));
        let result = unsafe { RegisterDragDrop(hwnd, target) };
        if result < 0 {
            unsafe { release(target) };
            return result;
        }
        guard.registered.insert(hwnd, target as usize);
        1
    }

    #[no_mangle]
    pub extern "system" fn syp_drop_poll(buffer: *mut u16, capacity: usize) -> usize {
        if buffer.is_null() || capacity < 2 {
            return 0;
        }
        let payload = match state().lock() {
            Ok(mut guard) => guard.queue.pop_front(),
            Err(_) => None,
        };
        let Some(payload) = payload else {
            return 0;
        };
        if payload.len() > capacity {
            let required = payload.len();
            if let Ok(mut guard) = state().lock() {
                guard.queue.push_front(payload);
            }
            return required;
        }
        unsafe {
            ptr::copy_nonoverlapping(payload.as_ptr(), buffer, payload.len());
        }
        payload.len()
    }

    #[no_mangle]
    pub extern "system" fn syp_drop_shutdown() {
        if let Ok(mut guard) = state().lock() {
            for (hwnd, target) in guard.registered.drain() {
                unsafe {
                    let _ = RevokeDragDrop(hwnd);
                    release(target as *mut DropTarget);
                }
            }
            guard.queue.clear();
            if guard.ole_initialized {
                unsafe { OleUninitialize() };
                guard.ole_initialized = false;
            }
        }
    }
}

#[cfg(target_os = "windows")]
pub use windows_drop::*;

#[cfg(not(target_os = "windows"))]
#[no_mangle]
pub extern "C" fn syp_drop_initialize() -> i32 {
    0
}

#[cfg(not(target_os = "windows"))]
#[no_mangle]
pub extern "C" fn syp_drop_register(_hwnd: isize) -> i32 {
    0
}

#[cfg(not(target_os = "windows"))]
#[no_mangle]
pub extern "C" fn syp_drop_poll(_buffer: *mut u16, _capacity: usize) -> usize {
    0
}

#[cfg(not(target_os = "windows"))]
#[no_mangle]
pub extern "C" fn syp_drop_shutdown() {}
