# Lab1 & Lab2 命令行编辑器

位置：`editor_cli/`

## 安装拼写检查库
```bash
pip install pyspellchecker
```
## 运行

```bash
python -m editor_cli.main
```

启动后进入交互式命令行，支持以下命令：

### 通用命令
- `load <file>`：加载文件（支持 `.txt` 和 `.xml`，不存在则新建）
- `save [<file>|all]`：保存当前/指定文件/全部
- `init <text|xml> [with-log]`：创建新缓冲区（支持指定类型，可在首行加 `# log`）
- `close [file]`：关闭当前/指定文件（若修改则提示保存）
- `edit <file>`：切换活动文件
- `editor-list`：列出打开文件（`*` 为活动，`[modified]` 为未保存，显示编辑时长）
- `dir-tree [path]`：显示目录树
- `undo` / `redo`：撤销/重做
- `log-on [file]` / `log-off [file]` / `log-show [file]`：日志控制与查看
- `exit`：退出并持久化工作区

### 文本编辑命令 (针对 .txt)
- `append "text"`：末尾追加一行
- `insert <line:col> "text"`：插入（支持多行）
- `delete <line:col> <len>`：删除（不可跨行）
- `replace <line:col> <len> "text"`：替换（支持多行）
- `show [start:end]`：显示文本
- `spell-check`：对当前文件进行拼写检查

### XML 编辑命令 (针对 .xml)
- `insert-before <tagName> <newId> <targetId> "text"`：在指定 ID 元素前插入新元素
- `append-child <tagName> <newId> <parentId> "text"`：在指定 ID 元素内追加子元素
- `edit-id <oldId> <newId>`：修改元素 ID
- `edit-text <id> "text"`：修改元素文本内容
- `delete <id>`：删除指定 ID 的元素
- `xml-tree [file]`：显示 XML 树结构

## 设计要点

### Lab 1
- 工作区（Workspace）管理多文件与活动文件，支持状态持久化（Memento，`.workspace_state.json`）
- 事件总线（Observer）发布命令事件；日志模块作为观察者写入 `.filename.log`
- 文本编辑器按行存储（`List[str]`），命令模式实现 `insert/delete/replace` 的 undo/redo

### Lab 2 新增特性
- **XML 编辑器**：支持 XML 树形结构的增删改查，同样基于命令模式实现 Undo/Redo。
- **统计模块**：使用观察者模式监听文件切换事件，统计每个文件的编辑时长。
- **拼写检查**：使用适配器模式（Adapter Pattern）集成拼写检查库（若未安装则使用 Mock 实现）。
- **日志增强**：支持在文件首行配置 `# log -e command1 command2` 来排除特定命令的日志记录。

## 说明

- 文件编码统一 UTF-8
- `save <file>` 与 `save all` 均支持；不带参数保存活动文件
- 未保存退出时逐一询问是否保存
- XML 文件必须包含根元素，且操作依赖唯一的 `id` 属性

## 测试

### 1. 文本编辑与拼写检查
```bash
# 加载（或创建）文本文件
load note.txt

# 写入内容（故意包含拼写错误 "eidtor"）
append "Welcome to the eidtor."
append "It supports xml and text."

# 查看当前内容
show

# 执行拼写检查
spell-check
# 预期输出: 第1行，第16列: "eidtor" -> 建议: editor ...

# 修正错误（将第1行第16列开始的6个字符替换为 "editor"）
replace 1:16 6 "editor"

# 验证修正结果
show

# 测试撤销与重做
undo
show
redo
show

# 保存文件
save
```

### 2. XML 编辑

```bash
# 加载（或创建）XML 文件
load library.xml

# 构建树结构（默认根节点 id="root"）
# 在 root 下追加一个 book 节点 (id=book1)
append-child book book1 root

# 在 book1 下追加 title 和 price 子节点
append-child title title1 book1 "Design Patterns"
append-child price price1 book1 "59.99"

# 查看 XML 树结构
xml-tree

# 修改文本内容（降价）
edit-text price1 "49.99"

# 在 book1 之前插入一本新书 (id=book2)
insert-before book book2 book1

# 为 book2 添加标题
append-child title title2 book2 "Clean Code"

# 再次查看树结构
xml-tree

# 删除 book1 及其子节点
delete book1
xml-tree

# 撤销删除操作
undo
xml-tree

# 保存 XML
save
```

### 3. 统计与日志

```bash
# 列出所有打开的文件及其编辑时长
editor-list

# 查看特定文件的详细统计
stats note.txt

# 开启日志记录
log-on note.txt

# 执行操作并查看日志
append "This line is logged."
log-show note.txt

# 查看当前工作区目录树
dir-tree

# 退出程序（自动保存工作区状态）
exit
```
