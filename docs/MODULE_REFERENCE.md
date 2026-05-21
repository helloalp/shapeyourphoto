# Module Reference

鏈枃璁板綍 1.2.6 褰撳墠鐪熷疄妯″潡鑱岃矗銆傛棫鐗堟湰鎻愬埌鐨勭嫭绔嬪崟鍥剧獥鍙ｃ€佸绔嬪幓鍣寜閽€佹櫘閫?`messagebox` 闀夸慨澶嶈鎯咃紝浠ュ強"鍏堣繍琛?setup 鍐嶈繍琛?start_app"鐨勫惎鍔ㄦ柟寮忓潎涓嶆槸褰撳墠涓昏矾寰勩€?
## 鍚姩涓庡竷灞€

### [ShapeYourPhoto.exe / tools/launcher/start.bat](/E:/aitools/shapeyourphoto/native/launcher)

姝ｅ紡鍙戝竷鍖呬富鍚姩鍏ュ彛鏄?`ShapeYourPhoto.exe`銆俙start.bat` 浠呬綔涓烘簮鐮佸寘鍜屾棫璺緞鍏煎鍏ュ彛锛屾壒澶勭悊鏈韩淇濇寔 ASCII-only锛屽彧璐熻矗鏌ユ壘 Python 骞惰繘鍏?`tools/launcher/start_helper.py`銆備笉寰楀姞鍏?benchmark銆佺洰褰曟壂鎻忔垨鏇存柊鍖呬笅杞姐€?
### [tools/launcher/start_helper.py](/E:/aitools/shapeyourphoto/tools/launcher/start_helper.py)

婧愮爜鍖呭惎鍔?helper銆傛樉绀轰腑鑻辨枃闃舵鎻愮ず锛屾鏌?Python 鐗堟湰銆佹鏌ヨ繍琛屼緷璧栥€佺己灏戜緷璧栨椂鎸夐渶鎵ц `python -m pip install -r requirements/runtime.txt`锛岀劧鍚庡惎鍔?`app.pyw` / `app.py`銆傛棫婧愮爜甯冨眬涓殑鏍圭洰褰?`requirements.txt` 浠呬綔涓哄吋瀹瑰洖閫€銆?
### [tools/legacy/](/E:/aitools/shapeyourphoto/tools/legacy)

淇濈暀鏃?`setup_deps.bat`銆乣start_app.bat` 鍜?`start_app.vbs` 浣滀负鍏煎鍏ュ彛銆傛棩甯稿惎鍔ㄤ笉闇€瑕佷娇鐢ㄣ€?
### [tools/entry/app.py](/E:/aitools/shapeyourphoto/tools/entry/app.py) / [tools/entry/app.pyw](/E:/aitools/shapeyourphoto/tools/entry/app.pyw)

婧愮爜鍖?GUI 钖勫惎鍔ㄥ櫒銆俙app.py` 灏?`src/` 鍔犲叆妯″潡鎼滅储璺緞锛岀劧鍚庡垱寤?Tk 鏍圭獥鍙ｃ€佽缃爣棰樹笌鍥炬爣銆佹寕杞?`PhotoAnalyzerApp` 骞跺眳涓€?
## 搴旂敤鍖?
### [src/ui_app.py](/E:/aitools/shapeyourphoto/src/ui_app.py)

涓荤獥鍙ｈ閰嶅拰楂樺眰鍗忚皟鍏ュ彛銆備繚鐣欏疄渚嬬姸鎬佸垵濮嬪寲銆佽彍鍗?wiring銆佸竷灞€銆佹嫋鎷藉畨瑁?鍗歌浇鍜岀獥鍙ｅ叧闂€傛壂鎻忋€佸垎鏋愩€佷慨澶嶃€佸垪琛ㄣ€丆onsole 鍜屽鏍哥粏鑺傞€氳繃 `src/ui_*` mixin 鎺ュ叆銆?
### [src/ui/](/E:/aitools/shapeyourphoto/src/ui)

UI 鍩虹璁炬柦鍖咃紝鍖呭惈绐楀彛鏍囬銆佽瑷€鐘舵€併€乨isplay mapping銆佷富棰樸€丠iDPI銆丼plash銆丒XIF 缂栬緫銆佹洿鏂板拰鍏憡寮圭獥銆傛柊澧炲叡浜?UI 鑳藉姏浼樺厛杩涘叆杩欓噷銆?
### [src/analysis/](/E:/aitools/shapeyourphoto/src/analysis)

鍒嗘瀽娴佹按绾垮寘銆俙core.py` 鎵胯浇涓诲垎鏋愭祦绋嬶紝`portrait.py` 鎵胯浇浜哄儚鍊欓€夊拰楠岃瘉锛宍discard.py` 鐢熸垚涓嶉€傚悎淇濈暀鍊欓€夛紙cleanup candidates锛夛紝`common.py` 鎻愪緵鍏变韩缁熻銆佹帺鑶滃拰璁℃椂宸ュ叿銆?
### [src/analyzer.py](/E:/aitools/shapeyourphoto/src/analyzer.py)

鍏煎钖勫叆鍙ｏ紝浠?re-export `analysis.analyze_image` 涓?`analysis.is_supported_image`銆傛柊澧炲垎鏋愰€昏緫涓嶅緱閲嶆柊鍫嗗洖杩欓噷銆?
### [src/repair_planner.py](/E:/aitools/shapeyourphoto/src/repair_planner.py)

鎶婂崟寮?`AnalysisResult` 鏄犲皠涓?`RepairPlan`銆傝鍒掑寘鍚?`method_ids`銆乣op_strengths`銆乣policy` 鍜?notes锛岄伩鍏嶆壒閲忓浘鐗囧叡鐢ㄧ粺涓€寮哄害銆?
### [src/repair_engine.py](/E:/aitools/shapeyourphoto/src/repair_engine.py) / [src/repair_ops.py](/E:/aitools/shapeyourphoto/src/repair_ops.py)

鎵ц淇閾惧拰鍏蜂綋鍥惧儚绠楀瓙銆傝繖閲屼細鐩存帴褰卞搷瑙嗚椋庢牸銆佽緭鍑哄畨鍏ㄥ拰鍏冩暟鎹繚鐣欙紝淇敼鍚庡繀椤昏皑鎱庨獙璇併€?
### [src/file_actions.py](/E:/aitools/shapeyourphoto/src/file_actions.py)

鐩綍鎵弿銆佸畨鍏ㄦ竻鐞嗗拰杈撳嚭璺緞鐢熸垚銆傛壂鎻忓繀椤婚伒瀹堝墠缂€銆佸悗缂€銆佸寘鍚笁绫绘枃浠跺す鍚嶇О蹇界暐瑙勫垯锛屾敮鎸佽繘搴﹀洖璋冨拰鍙栨秷浜嬩欢锛涘畨鍏ㄦ竻鐞嗗繀椤讳紭鍏堝洖鏀剁珯锛屽け璐ユ椂绉诲叆 `_cleanup_candidates`銆?
### [src/legacy_cleanup.py](/E:/aitools/shapeyourphoto/src/legacy_cleanup.py)

鍚姩鍑嗗闃舵鐨勬棫鐗堟湰娈嬬暀鏁寸悊妯″潡銆傚彧璇嗗埆鏃ф牴鐩綍妯″潡銆佹棫鍏ュ彛鍜屾棫杩愯缂撳瓨锛屽懡涓」绉诲叆 `data/update_quarantine/legacy_cleanup/` 骞剁敓鎴愭竻鍗曪紱鍙椾繚鎶ょ洰褰曘€佺敤鎴锋暟鎹€佹牱寮犮€佺鏈夋枃妗ｅ拰浠撳簱鏂囦欢蹇呴』璺宠繃銆?
### [src/gpu_accel.py](/E:/aitools/shapeyourphoto/src/gpu_accel.py)

GPU 鐘舵€佹帰娴嬨€乶ative backend 璋冪敤涓庝繚瀹堝洖閫€銆傝礋璐ｆ煡鎵鹃殢鍖呭垎鍙戠殑 `gpu/shapeyourphoto_gpu_core.exe`锛岄€氳繃 JSON / persistent worker 璋冪敤 Rust/wgpu 鍚庣鎵ц澶у浘浜害缁熻锛屽苟杈撳嚭璇婃柇 JSON锛沶ative 缁勪欢缂哄け銆佽秴鏃躲€佽澶囦笉鍙敤鎴栧皬鍥句换鍔′笉鍒掔畻鏃朵笉寰楀奖鍝嶅垎鏋愩€佷慨澶嶆垨璁剧疆椤垫墦寮€銆?### [native/gpu-core](/E:/aitools/shapeyourphoto/native/gpu-core)

ShapeYourPhoto 鑷甫 GPU core銆俁ust + wgpu 瀹炵幇锛屾櫘閫氱敤鎴蜂笉闇€瑕佸畨瑁?Rust銆丆UDA Toolkit銆乼orch銆丆uPy 鎴?OpenCV CUDA銆傚綋鍓嶆彁渚?`capabilities`銆乣self-test`銆乣luma-stats` 鍜?`serve`锛屾墦鍖呭悗浣嶄簬 `gpu/`銆?
### [src/stats_store.py](/E:/aitools/shapeyourphoto/src/stats_store.py)

缁熻鎸佷箙鍖栵紝鍐欏叆绯荤粺鐢ㄦ埛鏁版嵁鐩綍銆俉indows 浣跨敤鐢ㄦ埛绾?DPAPI 鍔犲瘑锛涙棫 `usage_stats.json` 鍙縼绉诲苟淇濈暀 migrated 澶囦唤銆?
### [src/app_metadata.py](/E:/aitools/shapeyourphoto/src/app_metadata.py)

搴旂敤鍚嶃€佺増鏈彿銆佸簲鐢ㄨ韩浠藉拰鍐呯疆鏇存柊鍘嗗彶銆傜増鏈崌绾у繀椤诲悓姝ヨ繖閲屻€佹牴 `docs/CHANGELOG.md` 鍜屽搴?`docs/updates/<version>.md`銆?
### [src/updater.py](/E:/aitools/shapeyourphoto/src/updater.py)

鍏煎 updater 鍏ュ彛锛屼繚鐣欐棫鐗堟湰鍜屾棫鏂囨。涓殑鍚姩璺緞銆傛柊鐗堜富绋嬪簭浼樺厛鍚姩 [src/updater_bootstrap.py](/E:/aitools/shapeyourphoto/src/updater_bootstrap.py)锛屽疄闄呭疄鐜颁綅浜?[src/updater_v2.py](/E:/aitools/shapeyourphoto/src/updater_v2.py)銆傛洿鏂?manifest 鐨?`managed_files` 搴斾娇鐢ㄥ綋鍓嶅竷灞€涓嬬殑鐩稿璺緞锛屼緥濡?`src/ui/cloud_actions.py`锛?.2.3/1.2.4 涓嶅啀閫氳繃鍐呯疆 updater 鐩村崌 1.2.5锛岀浉鍏虫琛€鍙戝竷浣跨敤鎵嬪姩涓嬭浇鎻愮ず manifest銆?
## 宸ュ叿涓庢瀯寤?
### [tools/benchmark/benchmark_test_images.py](/E:/aitools/shapeyourphoto/tools/benchmark/benchmark_test_images.py)

鏈湴 `test/` 鐪熷疄鍥剧墖 benchmark銆傝緭鍑?wall time銆亀orker cumulative銆乹ueue/wait銆佹參鍥俱€佹參闃舵銆佺浉浼兼娴嬭€楁椂銆侀棶棰樺浘鍜屼笉閫傚悎淇濈暀鍊欓€夋暟閲忋€俙test/` 涓虹┖鏃惰烦杩囷紱鎶ュ憡鍐欏叆琚拷鐣ョ殑 `benchmark_reports/`銆?
### [build/](/E:/aitools/shapeyourphoto/build)

PyInstaller銆両nno Setup 鍜?dmg 鏋勫缓閰嶇疆銆俙build/shapeyourphoto.spec` 浠嶄互鏍?`app.py` 涓哄叆鍙ｏ紝骞跺皢 `src/` 鍔犲叆鍒嗘瀽璺緞銆?
## 宸插簾寮冧絾闇€璁颁綇鐨勬棫鍏ュ彛

- 鐙珛 `single_image_window.py` 鍜?鍗曞浘妯″紡"涓嶆槸褰撳墠涓昏矾寰勶紱鍗曞紶鍥剧墖閫氳繃涓诲垪琛ㄥ鍏ャ€?- 瀛ょ珛"鍘诲櫔褰撳墠"鎸夐挳涓嶆槸褰撳墠涓昏矾寰勶紱闄嶅櫔鐢卞垎鏋愩€佷慨澶嶈鍒掑拰淇鎵ц閾剧粺涓€澶勭悊銆?- 鎵归噺淇闀胯鎯呬笉搴斿洖閫€鍒版櫘閫?`messagebox`锛涘簲缁х画浣跨敤 `repair_completion_dialog.py`銆?
