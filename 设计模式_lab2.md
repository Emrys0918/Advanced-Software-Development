# Lab2：基于字符命令界面的多文本编辑器

## 实验目标

本实验在Lab1的基础上要求实现一个**基于命令行的多文件编辑器**，包含**纯文本编辑器**与**XML编辑器**两类，增加**编辑时长统计、拼写检查**两大模块。



## 一、功能需求

### 1. 编辑器模块

#### XML编辑器 (XmlEditor)

**XML说明**:
XML (eXtensible Markup Language) 是一种用于存储和传输数据的标记语言，具有良好的可读性和可扩展性，广泛应用于配置文件、数据交换等场景。

**功能职责**:

- 支持元素级编辑操作：插入元素(insert-before)、追加子元素(append-child)、修改元素ID(edit-id)、修改元素文本(edit-text)、删除元素(delete)
- 支持树形结构的可视化输出(xml-tree)
- 支持拼写检查功能：扫描文档文本节点并输出拼写错误报告

**数据结构要求**:

- 解析XML文件为**树形结构**(DOM树)
- 内部维护元素节点，并建立 `id -> element` 的映射以支持快速查找
- 保存时序列化回XML格式

**建议使用的设计模式**:

- 命令模式 (Command)：实现undo/redo功能
- 组合模式 (Composite)：表示XML树形结构
- 装饰器模式 (Decorator)：自动标记文件修改状态

**XML文件示例**:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bookstore id="root">
    <book id="book1" category="COOKING">
        <title id="title1" lang="en">Everyday Italian</title>
        <author id="author1">Giada De Laurentiis</author>
        <year id="year1">2005</year>
        <price id="price1">30.00</price>
    </book>
    <book id="book2" category="CHILDREN">
        <title id="title2" lang="en">Harry Potter</title>
        <author id="author2">J K. Rowling</author>
    </book>
</bookstore>
```

**XML语法规则**:

1. `<?xml version="1.0" encoding="UTF-8" ?>` 必须写在首行(除非第一行是 `# log` 注释)
2. 根标签只能有一个，子标签可以有多个，且必须成对存在
3. 标签属性值必须用双引号包起来
4. **每个元素必须有唯一的 `id` 属性**，用于命令操作中的元素定位
5. 本次实验不考虑注释、自闭合标签等高级特性

**重要说明**:

- **要求所有元素都有id是为了简化实现**。在实际应用中XML元素不一定都有id，但在本实验中统一要求所有元素必须有唯一id

- **元素定位**：所有XML编辑命令中的元素ID参数都是指元素的 `id` 属性值，可以通过id精确定位任何元素

  

### 2. 统计模块 (Statistics)

**核心功能**：记录每个文件在当前会话(Session)中的编辑时长，并以可读格式显示。

**会话(Session)定义**:

- **会话**：从程序启动到退出的一次完整运行周期
- 每次启动程序开始新的会话，所有文件的编辑时长重置为0
- 工作区状态恢复不会恢复编辑时长

**时长计算规则**:

- **开始计时**：当文件成为活动文件时(通过 `load` 或 `edit` 命令)
- **停止计时**：当切换到其他文件、关闭文件或退出程序时
- **累计时长**：一个会话中，文件每次成为活动文件都会累计时长
- **重置时长**：文件关闭后，如果再次打开(`load`)，时长重置为0

**显示要求**:

- 在 `editor-list` 命令中，每个文件名后显示编辑时长
- 使用可读格式：根据时长大小自动选择合适单位

**时长格式规范**:

| 时长范围 | 显示格式   | 示例          |
| -------- | ---------- | ------------- |
| < 1分钟  | X秒        | `45秒`        |
| 1-59分钟 | X分钟      | `25分钟`      |
| 1-23小时 | X小时Y分钟 | `2小时15分钟` |
| ≥ 24小时 | X天Y小时   | `1天3小时`    |

**建议使用的设计模式**:

- 装饰器模式 (Decorator)：在显示文件列表时，为每个文件名添加时长信息
- 观察者模式 (Observer)：监听文件切换事件，自动更新时长统计

**说明**:

- 统计模块是相对独立的横切功能，不应与核心编辑功能强耦合
- 如果统计功能失败，应仅提示警告，不影响其他功能继续执行



### 3. 拼写检查模块 (Spell Checking)

> **核心考察点**：主要考察**架构设计能力**和**第三方库管理能力**，而非算法实现。

选择合适的拼写检查服务，实现对编辑器中的文本内容进行拼写检查，并报告错误。

可以考虑以下拼写检查服务：

API：https://dev.languagetool.org/public-http-api

Java：https://dev.languagetool.org/java-api

Python：`spell-checker`库或`pyspellchecker`库

**考察重点**:

1. **依赖隔离**：第三方库依赖被限制在适配器内
2. **接口抽象**：定义清晰接口，编辑器依赖接口而非实现
3. **依赖注入**：依赖从外部传入，而非内部创建
4. **可测试性**：使用Mock对象测试，无需真实库

**建议使用的设计模式**: 适配器模式 (Adapter)


### 4. 日志增强

日志模块在不改变核心行为的基础上，新增“按文件首行配置的日志过滤”能力。

- 核心功能：通过文件首行的 `# log` 行为该文件启用日志，并可追加参数过滤不需要记录的命令。
- 语法规则：
  - `# log`：启用该文件的日志记录（保持原有行为）。
  - `# log -e <cmd> [-e <cmd> ...]`：排除指定命令的日志记录，`-e` 可重复出现以排除多个命令。
- 示例：
  - 首行写入 `# log -e append -e delete` 表示不记录该文件的 `append` 与 `delete` 命令日志。
- 行为说明：
  - 过滤仅作用于该文件的日志记录，适用于文本编辑命令与XML编辑命令（例如 `insert-before`、`append-child` 等）。
  - 未识别或不存在的命令名将被忽略，并在日志模块内以告警方式提示；不影响程序正常运行。
  - 日志写入失败仅提示警告，不阻断编辑流程（与既有日志策略一致）。



## 二、 命令设计

### 命令速查表

在Lab2中，相比Lab1的命令集有以下**新增和变动**：

#### 工作区命令

| 命令                          | 功能                         | 必需参数 | 可选参数 |
| ----------------------------- | ---------------------------- | -------- | -------- |
| `init <text\|xml> [with-log]` | 创建新缓冲区，增加xml文件    | 文件类型 | with-log |
| `editor-list`                 | 显示文件列表（支持时长显示） | -        | -        |

#### XML编辑命令

| 命令                                              | 功能         | 适用文件 |
| ------------------------------------------------- | ------------ | -------- |
| `insert-before <tag> <newId> <targetId> ["text"]` | 插入元素     | .xml     |
| `append-child <tag> <newId> <parentId> ["text"]`  | 追加子元素   | .xml     |
| `edit-id <oldId> <newId>`                         | 修改元素ID   | .xml     |
| `edit-text <elementId> ["text"]`                  | 修改元素文本 | .xml     |
| `delete <elementId>`                              | 删除元素     | .xml     |
| `xml-tree [file]`                                 | 显示XML树    | .xml     |

#### 拼写检查命令

| 命令                 | 功能     | 适用文件  |
| -------------------- | -------- | --------- |
| `spell-check [file]` | 拼写检查 | .txt .xml |



### 2.1 工作区命令

#### 1. `init` - 创建新缓冲区

```bash
init <text|xml> [with-log]
```

**功能**：创建一个未保存的新缓冲文件，并初始化基础结构。

**参数说明**:

- `text`：创建纯文本文件
- `xml`：创建XML文件，写入合法的空结构
- `with-log`(可选)：是否在第一行添加 `# log` 以启用日志

**初始化内容**:

创建文本文件(`init text with-log`):

```txt
# log
```

创建XML文件(`init xml`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root id="root">
</root>
```

**说明**:

- 新缓冲区标记为已修改，需要使用 `save` 命令指定路径保存
- 创建后自动成为当前活动文件

#### 2. `editor-list` - 显示文件列表

```bash
editor-list
```

**功能**：显示工作区中所有打开的文件及其状态。

**显示格式(可选以下任一种)**:

**格式1**:

```
* file1.txt [modified] (2小时15分钟)
  file2.xml (45秒)
```

**格式2**:

```
> file1.txt* (2小时15分钟)
  file2.xml (45秒)
```

**说明**:

- **当前活动文件标记**：`*` (格式1)或 `>` (格式2)

- **已修改未保存标记**：`[modified]` (格式1)或后缀 `*` (格式2)

- **编辑时长**：括号内显示当前会话中的编辑时长

  

### 2.2 XML编辑命令

#### 1. `insert-before` - 插入元素

```bash
insert-before <tagName> <newId> <targetId> ["text"]
```

**功能**：在目标元素前(同级)插入一个新元素。

**参数说明**:

- `tagName`：新插入元素的标签名
- `newId`：新元素的唯一ID，不可与已有元素重复
- `targetId`：目标元素的ID，新元素将被插入到该元素前
- `"text"`：可选，新元素的文本内容

**异常处理**:

- `newId` 已存在：提示"元素ID已存在: [newId]"
- `targetId` 不存在：提示"目标元素不存在: [targetId]"
- 尝试在根元素前插入：提示"不能在根元素前插入元素"

**示例**:

```bash
insert-before book newBook book1 ""
```

#### 2. `append-child` - 追加子元素

```bash
append-child <tagName> <newId> <parentId> ["text"]
```

**功能**：在某元素内追加一个子元素(作为最后一个子元素)。

**参数说明**:

- `tagName`：要追加的子元素标签名
- `newId`：子元素ID，需唯一
- `parentId`：父元素ID
- `"text"`：可选，子元素的文本内容

**异常处理**:

- `parentId` 无效：提示"父元素不存在: [parentId]"
- `newId` 重复：提示"元素ID已存在: [newId]"

**示例**:

```bash
append-child price price4 book1 "29.99"
```

#### 3. `edit-id` - 修改元素ID

```bash
edit-id <oldId> <newId>
```

**功能**：修改某个元素的ID。

**参数说明**:

- `oldId`：原始ID，必须存在
- `newId`：目标ID，必须未被占用

**异常处理**:

- `oldId` 不存在：提示"元素不存在: [oldId]"
- `newId` 已被占用：提示"目标ID已存在: [newId]"
- 尝试修改根元素ID：提示"不建议修改根元素ID"

**示例**:

```bash
edit-id book1 book001
```

#### 4. `edit-text` - 修改元素文本

```bash
edit-text <elementId> ["text"]
```

**功能**：修改某元素的文本内容。

**参数说明**:

- `elementId`：元素的ID
- `"text"`：新文本内容(可选)，若为空字符串或省略则清空原内容

**异常处理**:

- `elementId` 不存在：提示"元素不存在: [elementId]"

**示例**:

```bash
edit-text title1 "New Book Title"
```

#### 5. `delete` - 删除元素

```bash
delete <elementId>
```

**功能**：删除指定ID的元素(包括其所有子元素)。

**异常处理**:

- `elementId` 不存在：提示"元素不存在: [elementId]"
- 尝试删除根元素：提示"不能删除根元素"

**示例**:

```bash
delete book1
```

#### 6. `xml-tree` - 显示XML树形结构

```bash
xml-tree [file]
```

**功能**：以树形结构打印XML文件内容，展示元素的层级关系、属性和文本内容。

**参数说明**:

- 不指定参数：显示当前活动文件
- `file`：显示指定XML文件

**适用对象**：仅适用于XML编辑器(`.xml` 文件)

**输出格式要求**:

- 使用树形字符(`├──`、`└──`、`│`)或缩进表示层级关系
- 显示元素的所有属性(包括id)
- 显示元素的文本内容(如果有)

**示例**:

原XML文件:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bookstore id="root">
    <book id="book1" category="COOKING">
        <title id="title1" lang="en">Everyday Italian</title>
    </book>
</bookstore>
```

输出:

```
bookstore [id="root"]
├── book [id="book1", category="COOKING"]
│   └── title [id="title1", lang="en"]
│       └── "Everyday Italian"
```



**说明**：两种格式均可，推荐使用树形字符以获得更好的可视化效果。显示类命令不改变文件状态，不进入撤销栈

#### 

### 2.3 拼写检查命令

#### 1. `spell-check` - 拼写检查

```bash
spell-check [file]
```

**功能**：检查文本文件、xml文件中的拼写错误。

**参数说明**:

- 不指定参数：检查当前活动文件
- `file`：检查指定文本文件

**输出格式参考**:

```
拼写检查结果:
第1行，第5列: "recieve" -> 建议: receive
第3行，第12列: "occured" -> 建议: occurred
```

```
拼写检查结果:
元素 title1: "Itallian" -> 建议: Italian
元素 author2: "Rowlling" -> 建议: Rowling
```

