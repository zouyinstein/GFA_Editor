<p align="center">
  <img src="frontend/app-icon.png" alt="GFA Editor app icon" width="96">
</p>

# GFA Editor v1.2

GFA Editor 是一个本地运行的 Bandage 风格 GFA 图查看和编辑工具。它支持 Cose、Band、Twin 三种视图，支持图编辑、alignment 可视化、本地/服务器文件管理，以及 GFA、FASTA、SVG 导出。

除非你主动配置服务器目录或使用 SFTP 传输，数据都保留在本机。

## License

GFA Editor 项目源码采用 **GNU Affero General Public License v3.0 or later** 授权，SPDX 标识为 `AGPL-3.0-or-later`。完整条款见 [LICENSE](LICENSE)，版权与第三方依赖说明见 [NOTICE](NOTICE)。

这意味着后续 fork、修改版或重新发布版本不能移除原始代码已有的 AGPL 授权义务；如果分发修改版，或以网络服务形式提供修改版，应按 AGPL 提供对应源码。第三方 vendor 文件保留其自身许可证。

## 快速启动

```bash
cd "/path/to/GFA_Editor"
scripts/setup_local_dev.sh
scripts/start_local.sh
```

打开：

```text
http://127.0.0.1:8000
```

停止服务：

```bash
scripts/stop_local.sh
```

如果 `8000` 端口被占用，可以换一个端口：

```bash
GFA_EDITOR_PORT=8010 scripts/start_local.sh
GFA_EDITOR_PORT=8010 scripts/stop_local.sh
```

如果启动时提示端口已占用，但 `/api/health` 没有响应，说明可能是其他本地进程占用了端口。查找并关闭：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

把 `8000` 替换成实际端口。如果不想关闭该进程，就换一个空闲端口启动 GFA Editor。

## 简要使用说明

1. 在左侧 Import 面板选择 `.gfa` 文件，点击 Load；也可以从顶部 Files 按钮打开服务器目录中的文件。
2. 顶部 Cose、Band、Twin 按钮用于切换三种可视化模式。
3. Display、Filters、Drawing、Labels、Files 用于调整显示、过滤、绘图范围、标签和文件来源。
4. 在图中选择 contig 或 link 后，在右侧 Inspector 中查看和编辑属性。
5. 顶部工具按钮支持 Undo、Redo、Delete、Delete All Selected、Duplicate、Merge、Rotate 和 Repeat resolution。
6. 左侧 Alignments 面板可以运行或导入比对结果，并用 `f`、`b` 和颜色按钮控制每条 query 的显示。
7. 顶部右侧导出按钮支持 GFA、FASTA、SVG 当前视图、selected 子图和 edit history JSON。

详细工具说明见 [doc/user_manual.md](doc/user_manual.md)。

## 桌面 App

安装桌面依赖：

```bash
scripts/setup_local_dev.sh --desktop
```

运行桌面封装：

```bash
scripts/run_desktop.sh
```

为当前平台打包：

```bash
scripts/build_desktop_app.sh
```

macOS 输出：

```text
dist/GFA_Editor.app
```

Windows 11 x86_64 打包：

```powershell
scripts\build_windows_exe.ps1
```

Windows 输出：

```text
dist\GFA_Editor\GFA_Editor.exe
```

Windows 分发时需要分享整个 `dist\GFA_Editor` 文件夹，不要只复制 `.exe`。

## Conda

```bash
conda env create -f environment.yml
conda activate gfa-editor
scripts/start_local.sh
```

Conda 环境包含 Python 依赖、`minimap2` 和 BLAST。

## Docker

```bash
docker build -t gfa-editor .
docker run --rm -p 8000:8000 -v "$PWD/server_data:/data/gfa-editor" gfa-editor
```

打开：

```text
http://127.0.0.1:8000
```

## Alignment 工具

运行 alignment 需要 `minimap2` 或 `blastn`。可用 conda 安装：

```bash
conda install -c bioconda minimap2 blast
```

为桌面版或 standalone 包收集工具：

```bash
scripts/collect_alignment_tools.sh
```

## 示例数据

```text
examples/mecat_mito_500K_before_rr.gfa
examples/simulated_reads/
```

## 数据目录

默认本地数据目录：

```text
server_data/
```

自定义本地数据目录：

```bash
GFA_EDITOR_DATA_DIR=/path/to/data scripts/start_local.sh
```
