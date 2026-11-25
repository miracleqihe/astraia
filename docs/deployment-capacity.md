# Astraia 发布容量与扩容

GitHub Pages 的限制针对整个发布站点，而不只是 `astraia/` 目录。2026-11-25 检查线上发布仓库当时的提交 `6617a120`：全部已跟踪文件合计约 790.8 MB（754.2 MiB），共 18,298 个文件；GitHub 所显示的仓库容量还包含 Git 对象和历史，不能与发布文件的原始大小直接比较。具体数值会随更新变化。

主要空间来源是知识页图片、历史故事分享图、内联图、图谱数据、旧版星图分片和手册 PDF。现存故事分享页面与对应图片应继续可访问，不要因节省空间直接删除旧地址或改写 Git 历史。

## 日常处理

1. Pages 工作流在生成 `_site` 后记录总字节数和文件数，达到 900,000,000 字节时发出警告；这是一条提前检查的提示，不是部署失败阈值。
2. 新增故事分享页保留各自的标题、摘要和链接，分享预览图由最多八张可复用图承担。旧分享图保留，因而不会突然回收已有空间，但未来增长更慢。
3. 优先检查重复产物、图片分辨率及构建时可复用的文件；删除历史文件之前先确认是否仍被分享链接、搜索引擎或旧版本客户端引用。

## 临近或超过限额时

GitHub 对已发布 Pages 站点的大小上限为 1 GB。到达上限前，应分阶段将大 PDF、知识图片及大型静态数据迁移到单独的对象存储或静态资源服务，先验证 HTTPS、跨域访问、数据完整性、费用与旧地址兼容，再更新前端资源地址。现有 Pages 主站可以保留。对象存储需要可管理的服务账号；如果使用自有域名，也需要域名及 DNS 管理权。Git LFS 不能直接用于 GitHub Pages 发布。

迁移到其他静态站点平台之前要核对文件数和单文件大小。例如 Cloudflare Pages 免费计划目前限制每个站点 20,000 个文件、每个资源 25 MiB；本项目当时已有 18,298 个文件，并有超过 25 MiB 的 PDF 和图谱数据，不能直接原样迁移。平台限额、存储配额和计费可能变化，实施时应重新核对。

官方说明：[GitHub Pages 限额](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)、[Git LFS 限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)、[Cloudflare Pages 限额](https://developers.cloudflare.com/pages/platform/limits/)、[Cloudflare R2 公开存储桶](https://developers.cloudflare.com/r2/buckets/public-buckets/)。
