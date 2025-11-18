# Lab1 命令行文本编辑器

位置：`editor_cli/`

## 运行

```bash
python -m editor_cli.main
```

启动后进入交互式命令行，支持以下命令（主要摘录）：

- `load <file>`：加载文件（不存在则新建并标记修改）
- `save [<file>|all]`：保存当前/指定文件/全部
- `init <file> [with-log]`：创建新缓冲区（可在首行加 `# log`）
- `close [file]`：关闭当前/指定文件（若修改则提示保存）
- `edit <file>`：切换活动文件
- `editor-list`：列出打开文件（`*` 为活动，`[modified]` 为未保存）
- `dir-tree [path]`：显示目录树
- `undo` / `redo`：撤销/重做
- `append "text"`：末尾追加一行
- `insert <line:col> "text"`：插入（支持多行）
- `delete <line:col> <len>`：删除（不可跨行）
- `replace <line:col> <len> "text"`：替换（支持多行）
- `show [start:end]`：显示文本
- `log-on [file]` / `log-off [file]` / `log-show [file]`：日志控制与查看
- `exit`：退出并持久化工作区（打开文件、活动文件、修改状态、日志开关）

## 设计要点

- 工作区（Workspace）管理多文件与活动文件，支持状态持久化（Memento，`.workspace_state.json`）
- 事件总线（Observer）发布命令事件；日志模块作为观察者写入 `.filename.log`
- 文本编辑器按行存储（`List[str]`），命令模式实现 `insert/delete/replace` 的 undo/redo
- 打开文件首行为 `# log` 时自动启用日志

## 说明

- 文件编码统一 UTF-8
- `save <file>` 与 `save all` 均支持；不带参数保存活动文件
- 未保存退出时逐一询问是否保存