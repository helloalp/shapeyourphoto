# Maintenance Guide

鏈枃鏄?1.2.6 褰撳墠缁存姢瑙勫垯銆傛棫鐗堟湰闄勫綍淇濈暀鍦?`docs/updates/`锛涘鏃ц鏄庝笌鏈枃鍐茬獊锛屼互鏈枃鍜屽綋鍓嶄唬鐮佷负鍑嗐€?

## 鍩烘湰鍘熷垯

1. 鍏堟牳浠ｇ爜锛屽啀鏀规枃妗ｆ垨瀹炵幇銆?
2. 灏忔淇敼銆佸彲楠岃瘉锛屼笉鍊熺淮鎶や换鍔￠噸鏋勬牳蹇冪畻娉曘€?
3. 淇濈暀鐢ㄦ埛鏁版嵁瀹夊叏杈圭晫锛氫笉涓婁紶鍥剧墖銆佷笉姘镐箙鍒犻櫎銆佷笉鏆楁敼杈撳嚭瑙勫垯銆?4. 鍔熻兘鍙樺寲蹇呴』鍚屾鏂囨。銆丆HANGELOG 鍜?`src/app_metadata.py`銆?5. 涓嶆彁浜ゆ湰鍦版牱寮犮€佺紦瀛樸€乸atch銆乣__pycache__`銆佽皟璇曡緭鍑烘垨涓存椂鏂囦欢銆?6. 涓嶅緱鍐欏叆闄愬埗浜у搧鏈潵鍙戝睍鏂瑰悜銆侀€傜敤浜虹兢銆佷娇鐢ㄥ満鏅€丄I 鑳藉姏鎺ュ叆鎴栦笓涓氬寲鍔熻兘鎵╁睍鐨勮〃杩帮紱浠讳綍鏂囨。淇敼銆佸鍒犮€佹洿鏂般€佸崌绾ч兘鍙兘鎻忚堪褰撳墠瀹炵幇浜嬪疄銆佸綋鍓嶅疄鐜扮害鏉熷拰褰撳墠瀹夊叏瑕佹眰锛屼笉鑳芥妸闃舵鎬у姛鑳界姸鎬佸啓鎴愰暱鏈熶骇鍝佽竟鐣屻€?7. 鏇存柊鍘嗗彶銆佹牴 README 鍜屽簲鐢ㄥ唴鐗堟湰璁板綍涓嶅緱鏆撮湶寮€鍙戣€呰澶囧瀷鍙枫€佺鏈夋祴璇曠幆澧冦€佸唴閮ㄤ緷璧栨爤銆丄I 鍗忎綔杩囩▼銆佹彁绀鸿瘝鎴栭€傜敤瀵硅薄鏍囩锛涚増鏈褰曞彧鍐欑敤鎴疯兘鎰熺煡鐨勫姛鑳界粨鏋滃拰瀹夊叏缁撴灉銆?
## 鍚姩閾捐矾淇濇姢

- 鏃ュ父鍚姩鍏ュ彛鏄彂甯冨寘鏍圭洰褰曠殑 `ShapeYourPhoto.exe`銆?- `start.bat` 浠呬綔涓烘簮鐮佸寘鍏煎鍏ュ彛锛屼繚鎸?ASCII-only 鍜岀煭閫昏緫锛氬彧鏌ユ壘 Python锛屽苟杩涘叆 `tools/launcher/start_helper.py`銆?- `tools/launcher/start_helper.py` 鍙互鍋氳交閲忕幆澧冩鏌ュ拰鎸夐渶渚濊禆瀹夎锛涗緷璧栭綈鍏ㄦ椂蹇呴』蹇€熻繘鍏?GUI銆?
- 涓嶅緱鎶?benchmark銆佺洰褰曟壂鎻忋€佹竻鐞嗐€佹洿鏂板寘涓嬭浇鎴栧叾浠栦笌鍚姩鏃犲叧鐨勯噸浠诲姟鏀惧叆鍚姩閾捐矾銆?
- `tools/legacy/setup_deps.bat` / `tools/legacy/start_app.bat` 鍙綔涓哄吋瀹瑰叆鍙ｏ紝鐢ㄦ埛鏂囨。涓嶅緱瑕佹眰鍏堣繍琛屽畠浠€?- 婧愮爜鍖呭湪鏃?Python 璁惧涓婁笉鑳界洿鎺ヨ繍琛岋紱`ShapeYourPhoto.exe` / `start.bat` 蹇呴』淇濈暀鍙鎻愮ず绐楀彛锛屼笉鑳介棯閫€銆?
## Tk 涓荤嚎绋嬭鍒?

- Tk 鎺т欢鍙兘鍦ㄤ富绾跨▼鏇存柊銆?
- 鍚庡彴绾跨▼涓嶅緱鐩存帴鍐?Treeview銆乀ext銆丩abel銆丳rogressbar 鎴栧脊绐椼€?
- 鐩綍鎵弿銆佹壒閲忓垎鏋愩€佹壒閲忎慨澶嶅拰鐩镐技妫€娴嬪簲閫氳繃鍥炶皟/闃熷垪/`root.after()` 鍥炰富绾跨▼銆?
- Console Text 鍒锋柊蹇呴』淇濇寔鍚堝苟鍒锋柊锛岄伩鍏嶆瘡鏉℃棩蹇楅噸缁樻暣鍧楀唴瀹广€?
- 鍒嗘瀽/淇杩涘害绐楀彛鍙樉绀哄浐瀹氶珮搴﹂樁娈垫憳瑕侊紱闀块樁娈佃鎯呭拰鎬ц兘缁嗚妭杩涘叆 Console锛屼笉寰楁拺寮€寮圭獥鍐呴儴甯冨眬銆?
- 杩涘害绐楀彛鍙厑璁镐竴涓槑纭彇娑堝叆鍙ｏ紝鍏抽棴鍙夊彿涓庢寜閽簲璧板悓涓€鍙栨秷璺緞銆?

## UI 涓荤被鎷嗗垎瑙勫垯

- `src/ui_app.py` 鍙礋璐ｄ富绐楀彛鐘舵€併€佹帶浠惰閰嶅拰楂樺眰鍗忚皟銆?
- 鎵弿/瀵煎叆銆佸垎鏋愪换鍔°€佷慨澶嶄换鍔°€佷富鍒楄〃銆丆onsole/perf銆佷笉閫傚悎淇濈暀鍊欓€?鐩镐技缁勫鏍稿垎鍒淮鎶ゅ湪 `src/ui_scan_actions.py`銆乣src/ui_analysis_actions.py`銆乣src/ui_repair_actions.py`銆乣src/ui_file_list.py`銆乣src/ui_task_console.py`銆乣src/ui_review_actions.py`銆?
- `src/ui/` 鍖呮壙杞界獥鍙ｆ爣棰樸€乨isplay mapping銆佷富棰樸€丠iDPI銆丼plash 鍜?EXIF 瀹夊叏缂栬緫绛夊叡浜?UI 鍩虹璁炬柦銆?
- 鏂板 UI 琛屼负鏃朵紭鍏堟斁鍏ュ搴?mixin 鎴?`src/ui/` 鍖咃紱鍙湁甯冨眬瑁呴厤銆佽彍鍗?wiring 鍜屾牴绐楀彛鐢熷懡鍛ㄦ湡閫傚悎鐣欏湪 `src/ui_app.py`銆?
- mixin 妯″潡涓嶅緱 import `ui_app.py`锛屽叡浜父閲忔斁鍦?`ui_constants.py`锛岄伩鍏嶅惊鐜緷璧栥€?
- 鎷嗗垎 UI 浠ｇ爜鏃跺繀椤讳繚鎸佸悗鍙板洖璋冨洖涓荤嚎绋嬨€乺un_id/cancel_event 闃叉棫鍐欏洖鍜?Console 鍚堝苟鍒锋柊瑙勫垯銆?

## 鍚庡彴绾跨▼銆乺un_id 涓庡彇娑堣鍒?

- 姣忚疆鎵归噺鍒嗘瀽閮藉簲鏈夊敮涓€ run_id銆?
- 鍙栨秷鍒嗘瀽閫氳繃 cancel_event 琛ㄨ揪銆?
- 鍚庡彴浠诲姟鍐欏洖缁撴灉銆佽繘搴︺€佷笉閫傚悎淇濈暀鎻愮ず銆佺浉浼煎浘鎻愮ず鎴栨渶缁堟憳瑕佸墠蹇呴』鏍￠獙 run_id 鍜?cancel_event銆?
- 鍙栨秷鍚庝繚鐣欐枃浠跺垪琛紝娓呯┖鏈疆鐩爣宸插啓鍏ョ殑缁撴灉銆侀敊璇€佽繘搴︺€佷笉閫傚悎淇濈暀鏍囪鍜岀浉浼肩粍鏍囪銆?
- 宸插彇娑?worker 鍙互瀹屾垚 CPU 宸ヤ綔锛屼絾缁撴灉蹇呴』涓㈠純銆?
- 姣忚疆鎵归噺淇涔熷簲鏈夊敮涓€ run_id 鍜?cancel_event銆?
- 鍙栨秷淇涓嶅緱娓呯┖淇鍓嶅凡缁忓瓨鍦ㄧ殑鍒嗘瀽缁撴灉銆侀敊璇€佷笉閫傚悎淇濈暀/鐩镐技鍥剧姸鎬佹垨淇寤鸿锛涘淇娴佺▼琛ュ垎鏋愪簡缂哄け鍥剧墖锛屽彇娑堟椂蹇呴』鎸変慨澶嶅墠蹇収鎭㈠銆?
- 淇鍙栨秷鍚庝笉寰椾繚鐣欏凡鍙栨秷鎵规鐨勫畬鎴愮粺璁°€佽皟璇曟墦寮€鍒楄〃鎴栦慨澶嶅畬鎴愯鎯呫€?
- 宸插啓鍑虹殑闈炶鐩栦慨澶嶈緭鍑哄繀椤诲垹闄わ紱鍒犻櫎澶辫触鏃剁Щ鍏?`_repair_canceled_outputs` 闅旂鐩綍骞舵彁绀恒€?
- 瑕嗙洊鍘熸枃浠朵慨澶嶉渶瑕佸厛鍒涘缓 `_repair_cancel_backups` 澶囦唤锛屽彇娑堟椂鎭㈠澶囦唤锛屾甯稿畬鎴愬悗娓呯悊澶囦唤銆?

## perf_timings / perf_notes 瑙勫垯

- 鍒嗘瀽鍜屼慨澶嶈€楁椂缁熶竴鍐欏叆 `perf_timings`銆?
- 闈㈠悜缁存姢鑰呯殑杞婚噺鐡堕鎻愮ず鍐欏叆 `perf_notes`銆?
- 涓嶈鏂板缓骞宠璁℃椂浣撶郴銆?
- 鍒嗘瀽寤鸿璁板綍璇诲彇銆丒XIF 杞銆亀orking image銆佸熀纭€缁熻銆佹洕鍏夈€侀攼搴︺€佽壊褰┿€佸櫔澹般€佷汉鍍忋€佷笉閫傚悎淇濈暀鍊欓€夈€佺浉浼煎浘妫€娴嬬瓑闃舵銆?
- 淇寤鸿璁板綍 planner銆佽鍙栥€佸悇 op銆佸€欓€夌敓鎴?璇勫垎銆佸畨鍏ㄦ鏌ャ€佷繚瀛樿緭鍑哄拰鍏冩暟鎹繚鐣欍€?
- Console 浠?`total_wall_time` 涓轰富锛沗worker_cumulative_time` 鏄苟鍙?worker 绱宸ヤ綔閲忥紝涓嶆槸鐢ㄦ埛绛夊緟鏃堕棿銆?
- 濡傛灉鍚屾椂鏄剧ず骞冲潎鑰楁椂锛屽繀椤诲尯鍒?`average_wall_time_per_image` 鍜?`average_worker_time_per_image`銆?
- 涓嶅緱鎶婃瘡寮犲浘鑰楁椂鐩稿姞鍚庝綔涓洪潰鍚戠敤鎴风殑"鏈疆鎬昏€楁椂"銆?

## EXIF Orientation 褰掍竴

- 璇诲彇鍥剧墖鏃朵娇鐢?`ImageOps.exif_transpose` 灏嗗儚绱犳柟鍚戣浆姝ｃ€?
- 淇濆瓨 JPEG/WebP 鍓嶅皢 EXIF Orientation 褰掍竴涓?`1`銆?
- 鍥炲綊鏃舵鏌ュ師鍥炬樉绀烘柟鍚戙€佽緭鍑虹墿鐞嗗昂瀵稿拰杈撳嚭 Orientation銆?

## 涓嶉€傚悎淇濈暀鍊欓€夊畨鍏ㄥ垹闄よ鍒?

- 涓嶉€傚悎淇濈暀鍊欓€夋槸寤鸿锛屼笉鏄嚜鍔ㄥ垹闄ゅ懡浠ゃ€?
- UI 榛樿涓嶅嬀閫夊€欓€夈€?
- 鍒犻櫎鍓嶅繀椤讳簩娆＄‘璁ゃ€?
- 鍒犻櫎蹇呴』璧?`safe_cleanup_paths()`銆?
- 浼樺厛绉诲叆绯荤粺鍥炴敹绔欙紱澶辫触鏃剁Щ鍏ラ」鐩唴 `_cleanup_candidates` 闅旂鐩綍銆?
- 涓嶅緱鍦ㄤ笉閫傚悎淇濈暀鎴栫浉浼煎浘澶嶆牳绐楀彛涓洿鎺?`unlink()` 鎴栨案涔呭垹闄ゃ€?

## 淇鐩爣闆嗗悎瑙勫垯

- "淇褰撳墠"鍙鍙栧綋鍓嶇劍鐐瑰浘鐗囥€?
- "鎵归噺淇鍕鹃€?浼樺厛浣跨敤鐪熸鐨?Treeview 澶氶€夐泦鍚堬紱鍙湁褰撳閫夋暟閲忓浜?1 寮犳椂鎵嶈涓烘壒閲忓閫夈€?
- 娌℃湁鐪熸澶氶€夋椂锛屾壒閲忓叆鍙ｅ洖閫€鍒板嬀閫夐泦鍚堬紱鍗曚釜钃濊壊楂樹寒琛屼笉寰楄鐩栧嬀閫夐泦鍚堛€?
- 鎵归噺淇蹇呴』閫愬浘璋冪敤 `repair_engine.repair_image_file()`锛屽苟璁?`repair_planner.build_repair_plan()` 鍩轰簬璇ュ浘鑷繁鐨?`AnalysisResult` 鐢熸垚 `method_ids`銆乣op_strengths` 鍜?policy notes銆?
- 涓嶅緱鎶婂綋鍓嶇劍鐐瑰浘鐨勬帹鑽愭柟娉曘€佸弬鏁版垨鍔涘害濂楃敤鍒版暣鎵瑰浘鐗囥€?
- 淇瀹屾垚璇︽儏鐨勬垚鍔熴€佽烦杩囥€佸け璐ャ€佸€欓€夊洖閫€/no-op 缁熻蹇呴』鏉ヨ嚜鐪熷疄鎵归噺鐩爣缁撴灉銆?

## 寮圭獥灏哄瑙勫垯

- 鍒嗘瀽/淇杩涘害銆佹壂鎻忓洓閫夐」銆佷慨澶嶅畬鎴愯鎯呫€佷笉閫傚悎淇濈暀鍊欓€夈€佺浉浼煎浘鍒楄〃銆佺浉浼煎浘缁勫唴瀵规瘮鍜岃缃獥鍙ｉ兘搴旀湁鏄庣‘ `minsize()` 鎴栧浐瀹?婊氬姩绛栫暐銆?
- 搴曢儴鍏抽敭鎸夐挳搴旀斁鍦ㄥ浐瀹氭寜閽尯锛屽唴瀹硅繃闀挎椂婊氬姩鍐呭鍖猴紝涓嶅帇缂╂寜閽尯銆?
- 杩涘害绐楀彛鐨勫簳閮ㄦ彁绀轰笌鍙栨秷鎸夐挳蹇呴』浣跨敤鐙珛甯冨眬鍗曞厓锛屼笉鑳戒簰鐩歌鐩栵紱鍏抽棴鍙夊彿蹇呴』绛夊悓鍙栨秷鎴栨槑纭鐢紝浣嗗彇娑堟寜閽繀椤诲彲杈俱€?
- 鍙缉鏀剧獥鍙ｈ揪鍒版渶灏忓昂瀵搁檮杩戞椂锛岀粺涓€鏄剧ず"宸茶揪鍒版渶灏忓彲鐢ㄧ獥鍙ｅぇ灏?銆?
- 浜岀骇绐楀彛榛樿灏哄蹇呴』鍙楀睆骞曞彲鐢ㄥ尯鍩熼檺鍒讹紝涓嶈兘涓轰簡灞曠ず瀹屾暣鍐呭瓒呭嚭灞忓箷銆?

## 鐩镐技鍥剧淮鎶よ鍒?

- 鐩镐技鍥惧彧浣滀负鍒嗘瀽鎵规闄勫姞缁撴灉銆?
- `SimilarImageGroup` 涓嶅啓鍥炲崟寮?`AnalysisResult.issues`銆乣scene_type`銆佷汉鍍忓瓧娈点€佷慨澶嶅缓璁垨涓嶉€傚悎淇濈暀鍊欓€夈€?
- 鍚屼竴寮犲浘鍙互鍚屾椂鍑虹幇鍦ㄤ笉閫傚悎淇濈暀鍊欓€夊拰 similar group 涓紱UI 鍙兘鎻愮ず锛屼笉鑷姩澶勭悊銆?
- 鐩镐技鍥惧垹闄ゅ鐢ㄥ叏灞€瀹夊叏娓呯悊銆?

## 璁剧疆涓庢壂鎻忚鍒?

- 搴旂敤璁剧疆缁熶竴鐢?`app_settings.py` 瀹氫箟銆佹牎楠屽拰淇濆瓨銆?
- UI 璁剧疆缁熶竴鐢?`settings_dialog.py` 绠＄悊锛屼笉鏂板闆舵暎鑿滃崟椤广€?
- Console 鏃堕棿妯″紡鍜屽瑙備富棰樹篃灞炰簬 app_settings schema锛屼笉鑳藉湪 UI 鍐呯鏈変繚瀛樸€?
- 鎵弿榛樿鑷冲皯蹇界暐 `_repair` 鍓嶇紑锛屼换鎰忓眰绾т互 `_repair` 寮€澶寸殑鐩綍閮借烦杩囥€?
- 鎵弿缁撴灉搴斿啓鍏?Console 绠€鎶ュ拰"鏈€杩戞壂鎻忔憳瑕?鏄庣粏锛涘畬鏁磋烦杩囩洰褰曟槑缁嗕笉寰楀埛灞忓埌 Console銆?
- 鎵弿鍜屾壂鎻忓悗鐨勫浘鐗囧姞杞介樁娈甸兘蹇呴』鏄剧ず杩涘害寮圭獥锛涙棤娉曢鐭ユ€绘暟鏃舵樉绀哄凡澶勭悊鏁伴噺锛屼笉閫犲亣杩涘害銆?
- 淇敼鎵弿閫昏緫鏃跺悓鏃堕獙璇佹寜閽壂鎻忋€佹嫋鎷芥枃浠跺す銆佽ˉ鎵€侀粯璁ゆ壂鎻忔ā寮忓拰蹇界暐鍓嶇紑銆?

## 鐢ㄦ埛鏁版嵁涓庣粺璁¤鍒?

- 鐢ㄦ埛鏁版嵁鍐欏叆琚拷鐣ョ殑 `data/` 鐩綍銆?
- 缁熻鍙繚瀛樿仛鍚堟暟鎹紝涓嶄繚瀛樺畬鏁村浘鐗囪矾寰勩€?
- Windows 浣跨敤鐢ㄦ埛绾?DPAPI 淇濇姢 `data/usage_stats.dpapi`锛涗笉鍙敤鏃朵笉寰楃敤 base64 鎴栫畝鍗曠紪鐮佸啋鍏呭姞瀵嗐€?
- 鏃?`usage_stats.json` 杩佺Щ鏃跺厛鍐欏叆鏂?store锛屾垚鍔熷悗淇濈暀 migrated 澶囦唤鎴栨爣璁帮紝涓嶇洿鎺ュ垹闄ゃ€?

## UI 鏄剧ず鍚嶈鍒?

- 鍐呴儴鑻辨枃 code/enum/storage 淇濇寔涓嶅彉銆?
- UI 閫氳繃 `ui/display_names.py` 鏄剧ず涓枃鎴栦腑鑻辩粨鍚堝悕绉帮紝涓嶆妸涓枃鍚嶅啓鍥炰笟鍔″垽鏂€?
- 鏈煡鍊煎繀椤绘樉绀轰负甯?raw value 鐨勫厹搴曟枃妗堬紝涓嶈兘寮傚父涓柇 UI銆?

## HiDPI 涓?EXIF 缂栬緫瑙勫垯

- Windows GUI 鍚姩鍓嶅惎鐢?DPI awareness锛孴k scaling 涓庣郴缁熷瓧浣撴寜 DPI 閰嶇疆銆?
- 鎵嬪伐楠屾敹 100% / 125% / 150% / 200% 缂╂斁涓嬩富绐楀彛銆佽缃€佽繘搴︺€佷慨澶嶈鎯呭拰 Console 瀛椾綋娓呮櫚搴︺€?
- ClearType銆佹樉鍗￠┍鍔ㄥ拰杩滅▼妗岄潰缂╂斁涓嶅畬鍏ㄥ彈搴旂敤鎺у埗锛屾枃妗ｉ渶璇存槑杈圭晫銆?
- EXIF 缂栬緫榛樿鍙锛屼繚瀛樺墠澶囦唤锛涘彧鍏佽鏍囬/鎻忚堪銆佷綔鑰呫€佺増鏉冦€佸叧閿瘝/澶囨敞绛夊畨鍏ㄦ枃鏈瓧娈点€?
- 绂佹淇敼鐩告満/闀滃ご銆佹媿鎽勬椂闂淬€丱rientation銆両CC 鍜屽唴閮ㄦ爣璁般€?

## GPU fallback 瑙勫垯

- GPU 鏄彲閫夊姞閫熻兘鍔涳紝涓嶆槸纭緷璧栥€?- 鏅€氱敤鎴蜂富璺緞蹇呴』浣跨敤闅忓寘鍒嗗彂鐨?native GPU backend锛屼笉寰楄姹傜敤鎴疯嚜琛屽畨瑁?CUDA銆乼orch銆丆uPy 鎴?OpenCV CUDA 鎵嶈兘鍚敤 GPU銆?- native backend 缂哄け銆佽澶囦笉鍙敤銆佽秴鏃舵垨浠诲姟瑙勬ā涓嶅垝绠楁椂锛屽簲鐢ㄥ繀椤绘甯稿惎鍔ㄥ苟鍥為€€ CPU銆?- 鍙湁 benchmark 璇佹槑鐪熷疄鏀剁泭鐨勪换鍔℃墠鑳介粯璁や娇鐢?GPU锛涘綋鍓嶅ぇ鍥惧垎鏋愪寒搴︾粺璁″彲璧?Rust/wgpu 鍚庣锛屽皬鍥俱€佷慨澶嶅€欓€夎瘎鍒嗗拰鐩镐技鍥剧缉鐣ョ壒寰佺户缁寜鎬ц兘闂ㄦ帶鍥?CPU銆?
## `/test` 鏈湴鏍峰紶瑙勫垯

- `test/` 鐢ㄤ簬鏈湴鐪熷疄鍥剧墖 benchmark 鍜屽洖褰掋€?
- 鍥剧墖鏂囦欢鐢?`.gitignore` 蹇界暐锛屼笉寰楁彁浜ゃ€?
- 鐪熷疄 `test/manifest.json` 涔熼粯璁ゅ拷鐣ワ紝鍥犱负鍙兘鍖呭惈鐢ㄦ埛鍥剧墖鏂囦欢鍚嶃€?
- 鍙彁浜ょ殑妯℃澘鏄?`test/manifest.example.json`銆?
- `tools/benchmark/benchmark_test_images.py` 蹇呴』鍏佽 `test/` 涓虹┖鏃跺畨鍏ㄨ烦杩囥€?
- benchmark 鎽樿搴旇褰?wall time銆亀orker cumulative銆乹ueue/wait銆佹參鍥俱€佹參闃舵銆佺浉浼兼娴嬨€侀棶棰樺浘鍜屼笉閫傚悎淇濈暀鍊欓€夋暟閲忋€?
- benchmark 鎶ュ憡鍐欏叆琚拷鐣ョ殑 `benchmark_reports/`锛屼笉寰楁彁浜ゆ姤鍛婃枃浠躲€?

## 鏂囨。鏇存柊瑙勫垯

- 涓嶅緱鍒犻櫎 `docs/`銆乣docs/technical/`銆乣docs/updates/`銆?
- 涓嶅緱娓呯┖姝ｅ紡鏂囨。銆?
- 杩囨椂鍐呭搴斾慨璁€佽縼绉汇€佹爣娉ㄥ巻鍙蹭笂涓嬫枃鎴栨寚鍚戝綋鍓嶈鏄庛€?
- 鏂板妯″潡鎴栬亴璐ｅ彉鍖栵細鏇存柊 `MODULE_REFERENCE.md`銆?
- UI 娴佺▼鍙樺寲锛氭洿鏂?`UI_AND_WORKFLOWS.md`銆?
- 鎶€鏈摼璺彉鍖栵細鏇存柊鎴栨柊澧?`docs/technical/` 涓撻銆?
- 浜у搧鍜岀晫闈㈣鑼冨彉鍖栵細鏇存柊鎴栨柊澧?`docs/specs/` 涓撻銆?
- 鐗堟湰鍗囩骇锛氭洿鏂?`docs/CHANGELOG.md`銆乣src/app_metadata.py` 鍜?`docs/updates/<version>.md`銆?

## 鐗堟湰璁板綍璇█瑙勮寖

- `src/app_metadata.py` 鍐呯疆 `CHANGELOG` 浼氬湪搴旂敤鍐呭睍绀猴紝榛樿蹇呴』浣跨敤涓枃涔﹀啓銆?- 鏍圭洰褰?`docs/CHANGELOG.md` 鍜?`docs/updates/<version>.md` 榛樿涔熶娇鐢ㄤ腑鏂囦功鍐欙紝骞朵笌 `app_metadata.CHANGELOG` 淇濇寔鍚屼竴浜嬪疄鍙ｅ緞銆?- 鍚屼竴涓増鏈彿鍦?`docs/CHANGELOG.md`銆乣src/app_metadata.py` 鐨?`CHANGELOG` / `CHANGELOG_I18N` 涓彧鑳芥湁涓€涓増鏈潡锛涚増鏈噯澶囨湡闂寸殑鍚庣画琛ュ厖蹇呴』杩藉姞鍒版棦鏈夌増鏈潡鐨?`items` 鍚庨潰锛屼笉寰楀洜涓烘棩鏈熴€佸垎鐐规暟閲忔垨闃舵涓嶅悓鏂板紑绗簩涓悓鐗堟湰鏉＄洰銆?- 鍐呴儴妯″潡鍚嶃€佹枃浠跺悕銆佸嚱鏁板悕銆佸瓧娈靛悕銆乧ode銆乪num銆乻torage key銆佺幆澧冨彉閲忓拰鍗忚瀛楁缁х画淇濈暀鑻辨枃鍘熸枃锛屼笉涓轰簡涓枃鍖栬€屾敼鍐欐妧鏈爣璇嗐€?- 濡傚繀椤诲紩鐢ㄨ嫳鏂囧簱鍚嶃€佸紓甯稿悕銆佸懡浠ゅ悕鎴栧崗璁瓧娈碉紝鍙洿鎺ヤ繚鐣欒嫳鏂囷紱瑙ｉ噴鎬ф枃妗堜粛浣跨敤涓枃銆?
- 鍙戝竷鍓嶆鏌?1.1.8 鍙婁箣鍚庣殑鏂板鐗堟湰璁板綍锛屼笉寰楀嚭鐜版暣鏉¤嫳鏂囨洿鏂拌鏄庢贩鍏ヤ腑鏂囩増鏈巻鍙层€?

## 鎺ㄨ崘楠岃瘉椤哄簭

1. `python -m compileall -q .`
2. 闈欐€佹鏌?`start.bat` / `tools/launcher/start_helper.py` 鏈姞鍏?benchmark銆佹壂鎻忋€佹洿鏂板寘涓嬭浇鎴栧叾浠栧惎鍔ㄦ棤鍏抽噸浠诲姟銆?
3. 鎼滅储鏃у叆鍙ｆ弿杩帮細`single_image_window`銆佸绔?鍘诲櫔褰撳墠"銆佹櫘閫?`messagebox` 闀夸慨澶嶈鎯呫€?
4. 妫€鏌ユ枃妗ｆ槸鍚﹀瓨鍦ㄦ槑鏄句贡鐮併€?
5. 妫€鏌?`git status --short`锛岀‘璁ゆ病鏈夋湰鍦版牱寮犮€乣__pycache__`銆乸atch銆乼mp 鎴?debug 杈撳嚭杩涘叆鐗堟湰鎺у埗銆?

## 楂橀闄╀慨鏀圭偣

- `src/ui_app.py` 涓?`src/ui_*` mixin锛氫富绾跨▼銆乺un_id銆佸彇娑堛€佸垪琛ㄥ埛鏂般€丆onsole 鍚堝苟鍒锋柊鍜屽脊绐楀叆鍙ｃ€?
- `src/analysis/core.py` / `src/analysis/portrait.py`锛氬垎鏋愮粨璁轰笌浜哄儚璇垽銆?
- `repair_ops.py` / `repair_engine.py`锛氳瑙夐鏍笺€佽緭鍑哄畨鍏ㄥ拰鍏冩暟鎹€?
- `file_actions.py`锛氭壂鎻忓拷鐣ャ€佹竻鐞嗗畨鍏ㄥ拰杈撳嚭璺緞銆?
- `app_settings.py`锛氳缃吋瀹广€侀粯璁ゅ€煎拰 worker 瑙勫垝銆?
- `similar_detector.py` / `similar_review_dialog.py`锛氱浉浼煎浘绠楁硶涓庡畨鍏ㄥ垹闄ゃ€?

# 1.2.5 缁存姢琛ュ厖璇存槑

- UI 鎵€鏈夊唴閮ㄥ悕璇嶅 `cleanup candidate`銆乣no-op` 绛夐潰鍚戠敤鎴峰睍绀烘椂蹇呴』閫氳繃 `display_names.py` 杞负"涓嶉€傚悎淇濈暀"銆?鏈敓鎴愭柊鐗堟湰"绛変腑鏂囷紱涓婅堪鏂囨。宸插皢鎻忚堪鏇存柊涓轰腑鏂囧寲璇嶆眹銆?
- `start.bat` 浠呬綔涓烘簮鐮佸吋瀹瑰叆鍙ｏ紝宸叉敮鎸佹寜闇€瀹夎 `requirements/runtime.txt` 涓殑渚濊禆锛堝寘鎷寮忎緷璧?`cryptography`锛夛紝浣嗕緷鐒剁姝㈠寘鍚换浣曞叾浠栭噸鍨嬫搷浣溿€?- 寮€鍙戣€呯鏈夋枃浠跺閮ㄧ讲娴佺▼銆丄I鍗忎綔鎻愮ず璇嶇瓑褰掓。浜?`private_docs/`锛屼弗绂佹彁浜ゅ埌鍏紑浠撳簱鎴栧彂鐗堝寘涓€?
- UI/浜戠鎿嶄綔鐩稿叧鐨勭綉缁滆皟鐢ㄥ繀椤绘斁缃簬鍚庡彴绾跨▼锛岃秴鏃跺拰閲嶈瘯蹇呴』涓嶉樆濉炰富鐣岄潰鐨勯噸缁樺拰鐢ㄦ埛鎿嶄綔锛屽叧闂獥鍙ｆ椂蹇呴』鑳藉畨鍏ㄥ垏鏂叧鑱斻€?

# 1.2.6 缁存姢琛ュ厖璇存槑

- 璁剧疆椤典繚瀛樺姩浣滃簲绔嬪嵆搴旂敤閰嶇疆浣嗕繚鐣欑獥鍙ｏ紝鏂逛究鐢ㄦ埛杩炵画璋冩暣锛涘彧鏈夊彇娑堟垨鍏抽棴鎵嶉€€鍑鸿缃〉銆?
- 鍙充晶棰勮鍥惧繀椤讳粠鍘熷浘鐢熸垚锛屼笉澶嶇敤鍒楄〃缂╃暐鍥撅紱棣栨閫夋嫨鍥剧墖鏃堕渶鍦ㄥ竷灞€绋冲畾鍚庨噸缁橈紝閬垮厤棣栧睆灏忓浘銆傝秴楂樻竻鍥剧墖棰勮搴旀寜鏄剧ず鍖哄煙闄嶉噰鏍疯В鐮侊紝鍚庡彴瀹屾垚鍍忕礌瑙ｇ爜锛屽苟缂撳瓨褰撳墠璺緞銆佸昂瀵稿拰鏂囦欢鏃堕棿鎴筹紝閬垮厤涓荤嚎绋嬬瓑寰呭畬鏁磋В鐮佹垨閲嶅瑙ｇ爜銆?
- 涓诲垪琛ㄧ缉鐣ュ浘缂撳瓨蹇呴』鏈夊閲忎笂闄愬苟甯︽枃浠舵椂闂存埑锛涘ぇ鏂囦欢澶规祻瑙堜笉鑳借 `PhotoImage` 缂撳瓨鏃犻檺澧為暱锛屽師鍥句慨鏀瑰悗涔熶笉鑳界户缁鐢ㄦ棫缂╃暐鍥俱€?
- 鍒楄〃銆佹竻鐞嗗鏍稿拰鐩镐技鍥惧鏍哥殑缂╃暐鍥惧簲鎸夌洰鏍囧昂瀵歌В鐮侊紝涓嶅緱涓轰簡灏忕缉鐣ュ浘瀹屾暣瑙ｇ爜澶?JPEG銆?
- GPU 鐘舵€佸繀椤诲尯鍒嗙‖浠舵娴嬨€乶ative 缁勪欢鏄惁闅忓寘瀛樺湪銆佸綋鍓嶄换鍔℃槸鍚﹀疄闄呬娇鐢ㄤ笁灞傘€傜‖浠跺彲瑙佷絾 native 缁勪欢缂哄け鏃剁户缁?CPU 鍥為€€锛屽苟鎻愮ず閲嶆柊瀹夎瀹屾暣鐗堟湰鎴栬幏鍙?GPU 缁勪欢鍖咃紝涓嶅緱鎶?Python GPU 渚濊禆浣滀负鏅€氱敤鎴蜂富瑙ｅ喅鏂规銆?- GPU 鍚庣鎺㈡祴蹇呴』浣跨敤鍏变韩鎬昏€楁椂棰勭畻锛屼笉鑳借澶氫釜鍙€夊簱涓茶绱Н瀹屾暣瓒呮椂銆?

---
> 涓嬫柟鍐呭涓烘棫鐗堟湰鐨勭淮鎶よ鑼冭嫳鏂囧巻鍙茶褰曪紝渚涜拷婧娇鐢ㄣ€?

# 1.1.8 Maintenance Addendum

- Settings additions must be defined in `app_settings.py` and surfaced from `settings_dialog.py`.
- Update and cloud-message UI orchestration lives in `ui/cloud_actions.py` and `ui/cloud_dialogs.py`; do not move protocol logic into `ui_app.py`.
- Developer mode is session-only and backed by `developer_mode.py`; never store an unlocked flag in `app_settings.json`.
- EXIF edits must preserve ShapeYourPhoto provenance fields and block any value containing `shapeyourphoto`.
- Startup scripts must stay fast; current source builds allow only on-demand runtime dependency installation from `requirements/runtime.txt`, and still forbid benchmarks, scans or update-package downloads during startup.
- GitHub auto-packaging workflow is paused in 1.1.8; release/server steps live in ignored private docs.

# 1.1.9 Maintenance Addendum

- Production update and cloud-message URLs are fixed internal constants. Do not expose them in Settings, do not persist them in ordinary `app_settings.json`, and do not add user-editable URL fields back.
- Settings pages shown to regular users should use short, understandable descriptions. Keep implementation notes in docs or private docs instead of user-facing labels.
- Theme settings may show theme names only; do not expose concrete color token values in the user settings dialog.
- The main window title format is `Shape Your Photo | v<version> | by Helloalp`.

# 1.2.0 Maintenance Addendum

- `cryptography` 鏄?updater 楠岀鐨勬寮忎緷璧栵紝蹇呴』閫氳繃 `requirements/runtime.txt`銆乣tools/launcher/start_helper.py` 鍜屾墦鍖呴厤缃繘鍏ュ彂甯冩祦绋嬨€?- 1.2.5 璧?`start.bat` 鍙互瑙﹀彂鎸夐渶渚濊禆瀹夎锛涗絾浠嶄笉寰楀姞鍏ユ洿鏂颁笅杞姐€乥enchmark銆佹壂鎻忔垨鍏朵粬鍚姩鏃犲叧閲嶄换鍔°€?
- 姝ｅ紡鍖呭簲鍖呭惈 `assets/update_public_key.pem`锛涘紑鍙戞祴璇曞彲鐢?`SHAPEYOURPHOTO_UPDATE_PUBLIC_KEY_FILE` 瑕嗙洊鍏挜鏂囦欢銆?
- `update_private_key.pem` 姘歌繙涓嶅緱杩涘叆浠撳簱銆佹簮鐮佸寘銆佸畨瑁呭寘鎴栨櫘閫氶」鐩洰褰曘€?
- 鏂囨。涓殑鍘嗗彶鐗堟湰鍙峰彲淇濈暀涓婁笅鏂囷紱涓嬩竴娆＄湡瀹?updater 娴嬭瘯娴佺▼浣跨敤 `1.2.0 -> 1.2.1`銆?
