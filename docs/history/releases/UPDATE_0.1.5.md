# fnAudio 0.1.5 更新说明

## 封面显示修复

- 修复 `/cover/<track_id>` 接口调用 `read_cover_for_item` 时缺少导入，导致请求被服务端直接关闭的问题。
- DSF/ DFF 内嵌 ID3 APIC 封面可以正常返回。
- FLAC 图片元数据和目录中的 `cover.jpg`、`folder.jpg` 等旁路封面继续使用统一读取逻辑。
- 前端所有本地封面引用统一通过绝对 URL 解析，适配 fnOS CGI 应用入口路径。
- 播放器底部封面、歌曲列表封面、歌词背景、歌词封面和 MediaSession 封面统一修复。

## 验证结果

- 测试环境音乐库识别 21 首歌曲。
- DSF 内嵌封面返回真实 JPEG。
- 目录 `Cover.jpg` 返回真实 JPEG。
- 封面接口请求无错误。
- Python 和前端 JavaScript 语法检查通过。
