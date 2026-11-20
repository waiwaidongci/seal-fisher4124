# Schema 版本

## v1
由 SQLAlchemy 模型定义，启动时经 `Base.metadata.create_all` 建表。本地小型应用不执行破坏性迁移；修改 schema 前请备份具名 `db-data` 卷。

## v2（漏封仪校准/盲验域，向后兼容新增）
新增四张表，不改动 v1 的任何既有表，旧 Fisher 研究照常运行：

- `leak_rolls`：卷材卷（`roll_code` 唯一；`occupied`/`revealed_by` 为揭晓硬占用标记）
- `leak_specimens`：卷内试件读数与人工复判（`(roll_id, specimen_key)` 唯一）
- `leak_rounds`：校准/盲验研究轮（软分配 JSON、冻结分界、盲验误判数、拒绝原因、状态机）
- `leak_jobs`：校准与揭晓异步任务（入队快照、结果、错误；worker 恢复去重补投）

并发揭晓的串行化依赖 `SELECT ... FOR UPDATE` 行锁（见 `src/services/leak_execution.py`），生产数据库为 MySQL 8；SQLite 仅用于本地测试，会忽略该子句。
