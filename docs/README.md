# ShapeYourPhoto 缁存姢鏂囨。

`docs/` 鏄?ShapeYourPhoto 鐨勬寮忕淮鎶ゆ枃妗ｇ洰褰曘€傚悗缁淮鎶よ€呭簲浠庤繖閲岀悊瑙ｉ」鐩紝涓嶈渚濊禆涓存椂 handover銆佽亰澶╂憳褰曟垨杩囨椂鏍规枃妗ｃ€?
## 鐩綍鍒嗗伐

- 鏍?[README.md](/E:/aitools/shapeyourphoto/README.md)锛氱敤鎴峰叆鍙ｃ€佸綋鍓嶈兘鍔涘拰缁存姢鏂囨。鍏ュ彛銆?- [MODULES.md](/E:/aitools/shapeyourphoto/docs/MODULES.md)锛氬揩閫熸ā鍧楃储寮曪紝渚夸簬鍏堝畾浣嶆枃浠躲€?- `docs/`锛氬綋鍓嶇淮鎶よ鍒欍€佺郴缁熸€昏銆佹ā鍧楀弬鑰冨拰 UI 宸ヤ綔娴侊紝鏄棩甯哥淮鎶ょ殑鏉冨▉璇存槑銆?- `docs/technical/`锛氫笓棰樻妧鏈枃妗ｏ紝璁板綍鍒嗘瀽閾捐矾銆佹€ц兘骞跺彂銆佺浉浼煎浘銆乧leanup銆佽缃壂鎻忕瓑璺ㄦā鍧楄鍒欍€?- `docs/specs/`锛氫骇鍝併€佺晫闈€佺敤鎴峰彲瑙佽瑷€銆佷俊鎭憟鐜般€丆onsole銆乨isplay mapping銆佺敤鎴锋暟鎹拰璁剧疆鎵╁睍瑙勮寖锛涗笉鏇夸唬 technical 鏂囨。銆?- `docs/updates/`锛氭寜鐗堟湰褰掓。鐨勬洿鏂拌褰曘€傛棫鐗堟湰鏂囨。淇濈暀鍘嗗彶涓婁笅鏂囷紱濡備笌褰撳墠琛屼负鍐茬獊锛屼互 1.2.6 鏂囨。鍜屼唬鐮佷负鍑嗐€?
## 寤鸿闃呰椤哄簭

1. [PRESERVATION_RULES.md](/E:/aitools/shapeyourphoto/docs/PRESERVATION_RULES.md)
2. [SYSTEM_OVERVIEW.md](/E:/aitools/shapeyourphoto/docs/SYSTEM_OVERVIEW.md)
3. [MODULE_REFERENCE.md](/E:/aitools/shapeyourphoto/docs/MODULE_REFERENCE.md)
4. [UI_AND_WORKFLOWS.md](/E:/aitools/shapeyourphoto/docs/UI_AND_WORKFLOWS.md)
5. [MAINTENANCE_GUIDE.md](/E:/aitools/shapeyourphoto/docs/MAINTENANCE_GUIDE.md)
6. [technical/README.md](/E:/aitools/shapeyourphoto/docs/technical/README.md)
7. [specs/README.md](/E:/aitools/shapeyourphoto/docs/specs/README.md)
8. [updates/README.md](/E:/aitools/shapeyourphoto/docs/updates/README.md)

## 褰撳墠缁存姢涓婚

1.2.6 鐨勬枃妗ｄ綋绯讳互杩欎簺褰撳墠浜嬪疄涓哄噯锛?
- `src/analyzer.py` 鏄吋瀹瑰叆鍙ｏ紝鍒嗘瀽涓婚€昏緫鍦?`src/analysis/` 鍖呫€?- 涓荤晫闈互涓诲垪琛ㄥ伐浣滄祦涓哄噯锛涙病鏈夌嫭绔嬪崟鍥剧獥鍙ｄ富璺緞銆?- 闄嶅櫔骞跺叆缁熶竴鍒嗘瀽鍜屼慨澶嶉摼锛涙病鏈夊绔?鍘诲櫔褰撳墠"涓诲叆鍙ｃ€?- 涓嶉€傚悎淇濈暀鍥剧墖鏄畨鍏ㄥ鏍告満鍒讹紝榛樿涓嶄慨澶嶃€佷笉鍒犻櫎锛屽垹闄ゅ繀椤讳簩娆＄‘璁ゅ苟璧板畨鍏ㄦ竻鐞嗐€?- 鐩镐技鍥炬槸鎵规绾ч檮鍔犵粨鏋滐紝涓嶅啓鍥炲崟寮?`AnalysisResult`銆?- 鎬ц兘璁℃椂缁熶竴鐢?`perf_timings` / `perf_notes`锛孋onsole 鍙仛鍚堝苟鍚庣殑鐢ㄦ埛鍙鎽樿銆?- GPU 鏄簲鐢ㄨ嚜甯︾殑鍙€?native 鍔犻€熻兘鍔涳紝涓嶈兘鎴愪负纭緷璧栵紱缂哄皯 native 缁勪欢鎴栬澶囦笉鍙敤鏃跺繀椤昏嚜鍔ㄥ洖閫€ CPU銆?- 褰撳墠涓荤嚎锛歎I mixin 宸叉媶鍒嗗埌 `ui_*.py`锛沗src/ui/` 鎵挎帴 UI 鍩虹璁炬柦锛沗updater_v2.py` 鏄綋鍓?updater 涓诲疄鐜帮紱`cryptography` 鏄寮忎緷璧栵紱鍙戝竷鍖呭惎鍔ㄥ叆鍙ｆ敹鏁涘埌 `ShapeYourPhoto.exe`锛宍start.bat` 浠呬繚鐣欐簮鐮佸寘鍏煎锛涘唴閮?code/enum 閫氳繃 `ui/display_names.py` 鏄犲皠涓虹敤鎴峰彲璇讳腑鏂囨樉绀哄悕銆?- 1.2.6 鏂板锛氳缃繚瀛樺悗涓嶅叧闂獥鍙ｏ紱鍙充晶棰勮鍥句細鍦ㄥ竷灞€绋冲畾鍚庝粠鍘熷浘閲嶇粯锛屽苟閬垮厤瓒呴珮娓呭浘鐗囬噸澶嶅畬鏁磋В鐮侊紱GPU 璇存槑鍖哄垎纭欢鍙銆侀殢鍖?native 缁勪欢鍜屽疄闄呬换鍔′娇鐢ㄧ姸鎬侊紝澶у浘鍒嗘瀽浜害缁熻鍙嚜鍔ㄨ皟鐢?native backend銆?
## 鏂囨。缁存姢瑙勫垯

- 涓嶅緱鍒犻櫎 `docs/`銆乣docs/technical/`銆乣docs/updates/`銆?- 涓嶅緱娓呯┖姝ｅ紡鏂囨。銆?- 鏃у唴瀹逛笉閫傜敤鏃讹紝搴斾慨璁€佽縼绉汇€佹爣娉ㄥ巻鍙蹭笂涓嬫枃锛屾垨鎸囧悜褰撳墠璇存槑銆?- 涓嶅緱鍦ㄥ叕寮€鎴栫鏈夋枃妗ｄ腑鍔犲叆闄愬埗浜у搧鏈潵鍙戝睍鏂瑰悜銆侀€傜敤浜虹兢銆佷娇鐢ㄥ満鏅€丄I 鑳藉姏鎺ュ叆鎴栦笓涓氬寲鍔熻兘鎵╁睍鐨勮〃杩帮紱浠讳綍鏂囨。淇敼銆佸鍒犮€佹洿鏂般€佸崌绾ч兘搴旀弿杩板綋鍓嶄簨瀹炪€佸綋鍓嶅畨鍏ㄨ鍒欏拰宸插疄鐜拌涓猴紝涓嶅簲鎶婇樁娈垫€х姸鎬佸啓鎴愰暱鏈熶骇鍝佽竟鐣屻€?- README銆丆HANGELOG銆乣docs/updates/` 鍜?`src/app_metadata.py` 涓殑鏇存柊鍘嗗彶涓嶅緱鍐欏叆寮€鍙戣€呰澶囧瀷鍙枫€佺鏈夋祴璇曠幆澧冦€佸唴閮ㄤ緷璧栨爤缁嗚妭銆佺淮鎶よ繃绋嬨€丄I 鍗忎綔杩囩▼鎴栭€傜敤瀵硅薄鏍囩锛涘彧璁板綍鐢ㄦ埛鍙悊瑙ｇ殑鍔熻兘鍙樺寲銆佷綋楠屽彉鍖栧拰瀹夊叏缁撴灉銆?- 鍔熻兘銆佹ā鍧椼€佽缃垨鐗堟湰鍙樺寲鏃讹紝鍚屾鏇存柊 `docs/CHANGELOG.md`銆乣src/app_metadata.py` 鍜屽搴?`docs/updates/<version>.md`銆?- 鐗堟湰璁板綍榛樿浣跨敤涓枃锛歚app_metadata.CHANGELOG`銆佹牴 `docs/CHANGELOG.md` 鍜?`docs/updates/<version>.md` 蹇呴』淇濇寔涓枃浜嬪疄鍙ｅ緞涓€鑷达紱鑻辨枃浠呬繚鐣欏湪鏂囦欢鍚嶃€佸嚱鏁板悕銆佸崗璁瓧娈点€佺幆澧冨彉閲忓拰鍐呴儴 code/enum 绛夋妧鏈爣璇嗕腑銆?- 鍚屼竴涓増鏈彿鍙兘鏈変竴涓増鏈褰曞潡锛涘悗缁ˉ鍏呭簲杩藉姞鍒版棦鏈夋潯鐩悗闈紝涓嶅緱鎷嗘垚澶氫釜鍚岀増鏈褰曘€?
# 1.1.9 Documentation Note


See also `docs/updates/1.1.9.md`, `docs/technical/UPDATES_AND_CLOUD.md`, and `docs/technical/UI_SETTINGS_DATA.md`.

# 1.2.6 鏂囨。璇存槑

鍙傝 `docs/updates/1.2.6.md`銆乣docs/technical/UPDATES_AND_CLOUD.md` 鍜?`docs/technical/UI_SETTINGS_DATA.md`銆?
