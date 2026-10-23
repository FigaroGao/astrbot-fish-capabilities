# 表情索引与限频

[English — 完整翻译](memes.en.md)

目录：`AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/memes/`，其中 `manifest.json` 是数组。每条包含 `id/category/file/tags/description/image_text/usage_notes/approved/sha256`。图片放分类目录，路径相对于图库根目录。

八类：happy 开心、comfort 安慰、tease 吐槽调侃、confused 疑惑、greeting 打招呼、goodnight 晚安、sad 难过、acknowledge 收到回应。

使用项目根目录的本地导入工具（不会发送消息）：

```bash
python -m tools.import_meme /path/to/approved.png --library /path/to/AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/memes --category happy --tags '开心,庆祝' --description '表达开心和庆祝' --approve
```

导入后人工补充 `image_text`（实际文字）和 `usage_notes`（适合/不适合场景），确保含义准确。原图标题不能当作已核实 OCR。工具会校验格式、4MB 上限与重复图片；运行时还校验批准状态、路径及 SHA256。

模型先查 `fish_meme_catalog(category, query)`，按标签、实际文字和场景检索，再通过 `fish_meme(category, meme_id)` 选择确切图片。不是每条消息再调用视觉模型，也不是达到次数就强制随机发图。

0.4.0 默认取消轮次间隔和时间冷却（两者均为0）；每小时最多六张，同图一小时不重复，一轮最多一张，由模型选择是否发及具体图片。已有安装需手动将 meme_min_reply_gap 和 media_cooldown_seconds 设为0。可自行调回较严格的间隔；显式索要只跳过软间隔，仍保留单轮、小时与同图限制。

参考图库：[deepseek-chan-meme-pack](https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack)。本仓库不再分发第三方图片，使用者自行核对来源及授权并导入。原设备的 74 张工作图库不包含在安装包内。
