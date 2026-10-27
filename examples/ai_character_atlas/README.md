# AI拟人形象资料卡 / AI character reference cards

[中文功能说明](../../docs/release-0.8.0.md#选择式视频与角色) · [Full English guide](../../docs/release-0.8.0.en.md#selective-video-reading-and-characters)

7张资料卡，最多3张优先参考接入概览视觉调用。仅附文字、来源URL及校验值，不含图片、私人路径、身份绑定或Embedding。取得素材时须核对各自许可并保留作者署名；公开可见不等于允许再分发。Pixiv原页本次无法直接访问，相关作者图借有来源的归档核对；OpenPet其他版本仅作索引，未作为已核准可再分发素材。

本机插件数据目录下创建`character-atlas`，放`cards.json`及按其references中file命名的合法参考图；SHA256需一致。打开`bili_character_enabled`。没有有效图时不会假装识别。角色外观不等于账号，小鲸/姐姐不是通用形象别名。参考匹配不是未见样本准确率基准。

Seven text cards; up to three priority references join the overview visual call. Only descriptions, source URLs, and checksums are included: no image bytes, private paths, account binding, or embeddings. Check each source's terms and retain attribution; public visibility is not redistribution permission. The original Pixiv page was unavailable in this research, so attributed archives were used to inspect those author images. Other OpenPet variants are indexed only, not treated as cleared for redistribution.

Create `character-atlas` under the plugin's local data directory. Add `cards.json` and lawfully obtained reference images named by each references.file field, with matching SHA256. Enable `bili_character_enabled`. Missing valid images do not produce a pretend recognition setup. Appearance is not account identity; Xiaojing/sister are not generic character aliases. Reference matching is not an unseen-sample accuracy benchmark.
