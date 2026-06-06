# GFA Editor v1.2 用户手册

本文档说明 GFA Editor v1.2 中主要工具的用途和操作方式。GFA Editor 面向本地 GFA assembly graph 的查看、编辑、比对结果可视化和导出。

## 1. 启动、停止和数据安全

启动本地浏览器版：

```bash
scripts/start_local.sh
```

打开：

```text
http://127.0.0.1:8000
```

停止：

```bash
scripts/stop_local.sh
```

如果 `8000` 端口被占用：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

也可以不关闭已有进程，改用其他端口：

```bash
GFA_EDITOR_PORT=8010 scripts/start_local.sh
```

GFA Editor 默认只在本机读写数据。只有当你明确使用 Files 中的服务器目录或 SFTP 功能时，才会与外部路径或远程服务器交互。

## 2. 界面结构

顶部栏左侧显示 app 图标、`GFA Editor v1.2` 和当前文件名。顶部中间是可视化模式和工具按钮。顶部右侧是编辑和导出按钮。

左侧面板包含 Stats、Import、Labels、Alignments。

中间是 graph workspace。右侧是 Inspector、Operation Log 和 Edit History。

## 3. Import

在 Import 面板中选择 `.gfa` 文件，然后点击 Load。

`Keep sequences for GFA/FASTA export` 用于保留 segment sequence。如果后续需要导出 FASTA 或带 sequence 的 GFA，建议保持勾选。只有在图很大且不需要 sequence 导出时才建议关闭。

也可以通过顶部 Files 按钮从本地 server data 目录或 SFTP 路径加载图文件。

## 4. 三种可视化模式

Cose 是力导向布局，适合快速查看连接关系。

Band 是 Bandage 风格布局，contig 以较粗的路径显示，link 以箭头连接。

Twin 会并排显示 Cose 和 Band，适合对比拓扑关系和路径形态。

Fit 按钮会把当前可见图居中并适配窗口。

Draw 按钮用于重新绘图。Drawing 设置中可以选择绘图范围：

- Entire graph：重绘整个图
- Visible/filter result：只重绘当前可见或过滤后的图
- Selected neighborhood：只重绘当前选择 contig 的邻域

`Redraw after edits` 会在编辑后自动重绘。

## 5. Display、Filters、Labels、Files

Display 用于调整 zoom、circle size、contig width 和 link width。

Filters 用于搜索 contig、选择 partial/exact 匹配方式、设置最小 depth，以及选择颜色模式。颜色模式包括 depth、alignment identity、long-read paths、degree 和 random。

Labels 用于控制显示哪些文字：

- Name
- Length
- Depth
- Alignments
- Link label
- Text outline

Files 包含本地 server data 和 SFTP 操作。可以刷新文件列表、加载 server GFA、保存当前图到 server data 目录、从 SFTP 下载、上传到 SFTP。

## 6. 选择和 Inspector

点击 contig 或 link 可以选择对象。不同视图下支持的多选方式和可用操作会根据当前选择自动启用或禁用。

Inspector 会显示 ID、label、length、depth、degree、support、CIGAR、tags，以及可用的最佳 alignment 或 path 信息。

Edit contig 可修改：

- Name
- Label
- Colour
- Depth

修改 Name 会重写 GFA 中的 `S` record，并同步更新相关 `L` record。

Edit link 可修改：

- Label
- Colour
- Support RC
- CIGAR

link 的 label 和 colour 会保存为 `LB:Z` 和 `CL:Z` tag。

## 7. 编辑工具

Undo 和 Redo 用于撤销或重做图编辑。

Delete 删除当前选择。

Delete All Selected 删除所有选中的 contig 和 link。

Duplicate 复制选中的 contig 以及相关 link。

Merge 用于合并选中的 link，或合并一条已选择的连通路径。Cose 和 Band 视图中，merge 后只会调整被 merge 的 contig 和相关 link，未参与 merge 的 contig 和 link 会尽量保持原位置，减少整张图跳动。

Rotate 用于调整 circular contig 的起点。

Repeat A 和 Repeat B 用于 repeat resolution。通常先 Duplicate repeat contig，再使用 Repeat A/B 执行不同策略。

Operation Log 记录近期操作。

Edit History 可以导出、导入、推断、渲染和回放编辑历史。

## 8. Alignments

Alignments 支持 `minimap2` 和 `blastn`。

运行 alignment：

1. 先加载 GFA。
2. 选择 Tool。
3. 选择 Preset。
4. 选择 query FASTA/FASTQ。
5. 点击 Run。

Advanced 中可以设置 extra args、导入结果格式、结果映射方向、查看生成的命令，并导入已有 PAF 或 BLAST outfmt 6 文件。

Read 下拉框可以显示 All reads，也可以只查看单条 query/read。

比对颜色控制：

- `Light hit background` 控制 alignment/read-path 颜色模式下是否允许显示命中 contig 的浅色背景。
- Query colours 中每条 query 都有 `f`、`b` 和颜色选择器。
- `f` 表示 foreground，控制该 query 的深色命中片段是否显示。
- `b` 表示 background，控制该 query 是否参与浅色命中背景。
- 单条 query 时，可以显示浅色命中 contig 背景，同时保留深色命中区段。
- 取消单条 query 的 `b` 后，不显示浅色背景，只显示深色命中区段。
- 多条 query 时，默认不显示每条 query 的浅色背景，深色命中区段按 query 使用不同颜色。
- 所有命中 contig 的浅色背景使用统一浅色，以便和全图未命中的浅灰背景区分，避免多条 query 的浅底难以判断。

例如三条 query 可以分别显示红、蓝、绿的深色命中片段；如果开启背景，只用统一浅色标记这些 contig 曾被命中。

## 9. Export

顶部右侧快速导出按钮会用默认文件名保存当前图。

Export options 中包含：

- Format：GFA、FASTA、SVG image
- Save graph：选择路径和文件名保存当前图
- Save SVG view：保存当前视图为 SVG 图片
- Selected：导出 selected links 或 selected SVG 内容
- History：导出 edit history JSON

浏览器模式中，导出会弹出保存文件对话框，可选择路径并重命名，而不是立即下载。

macOS standalone app 中，导出会连接系统文件选择器，可选择保存位置和文件名。

SVG 导出会保留当前 Cose、Band 或 Twin 视图中的可见 label、颜色和 alignment foreground 命中片段。

## 10. 桌面版和 standalone 打包

构建 macOS app：

```bash
scripts/setup_local_dev.sh --desktop
scripts/build_desktop_app.sh
```

输出：

```text
dist/GFA_Editor.app
```

在 Windows 11 x86_64 上构建 Windows executable：

```powershell
scripts\build_windows_exe.ps1
```

输出：

```text
dist\GFA_Editor\GFA_Editor.exe
```

Windows 分发时需要分享整个 `dist\GFA_Editor` 文件夹，因为其中包含运行时、frontend 文件、示例数据和打包的 alignment tools。

app 图标源文件是：

```text
packaging/icons/GFA_Editor_source.png
```

重新生成图标：

```bash
python scripts/generate_app_icons.py
```

该脚本会生成 frontend 使用的 PNG、macOS `.icns`、Windows `.ico` 和 iconset PNG 文件。

## 11. 常见问题

端口占用时，先尝试：

```bash
scripts/stop_local.sh
```

如果不是 GFA Editor 自己占用端口，用：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

alignment 运行失败时，检查 `minimap2` 或 `blastn` 是否已安装，或者是否已收集到：

```text
packaging/bin/<platform>/
```

桌面版没有打开内嵌窗口而转为浏览器模式时，查看日志：

```text
~/GFAEditorData/desktop.log
```

未签名 macOS 本地构建可能需要右键 Open，或清除 quarantine：

```bash
scripts/macos_clear_quarantine.sh dist/GFA_Editor.app
```
