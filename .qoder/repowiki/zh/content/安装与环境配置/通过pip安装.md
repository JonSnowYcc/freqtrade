# 通过pip安装

<cite>
**本文档中引用的文件**  
- [setup.sh](file://setup.sh)
- [setup.ps1](file://setup.ps1)
- [requirements.txt](file://requirements.txt)
- [requirements-dev.txt](file://requirements-dev.txt)
- [requirements-hyperopt.txt](file://requirements-hyperopt.txt)
- [requirements-plot.txt](file://requirements-plot.txt)
- [requirements-freqai.txt](file://requirements-freqai.txt)
- [requirements-freqai-rl.txt](file://requirements-freqai-rl.txt)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构概览](#项目结构概览)
3. [核心安装流程](#核心安装流程)
4. [setup.sh 脚本详解（Linux/macOS）](#setupsh-脚本详解linuxmacos)
5. [setup.ps1 脚本详解（Windows）](#setupps1-脚本详解windows)
6. [requirements 文件功能解析](#requirements-文件功能解析)
7. [虚拟环境管理与激活](#虚拟环境管理与激活)
8. [常见问题与解决方案](#常见问题与解决方案)
9. [验证安装](#验证安装)
10. [总结](#总结)

## 简介

Freqtrade 是一个免费开源的加密货币交易机器人，支持通过 Telegram 或 WebUI 进行控制。本文档旨在提供一份详尽的 pip 安装指南，涵盖从创建虚拟环境到安装主程序的完整流程。我们将深入解析 `setup.sh`（Linux/macOS）和 `setup.ps1`（Windows）脚本的使用方法，说明如何选择性安装开发依赖、Hyperopt、FreqAI 和绘图组件，并解释不同 `requirements` 文件的功能与区别。

**Section sources**
- [README.md](file://README.md#L1-L229)

## 项目结构概览

Freqtrade 项目结构清晰，主要组件包括：
- **freqtrade/**: 核心源代码目录
- **user_data/**: 用户配置、策略和回测结果
- **scripts/**: 辅助脚本
- **tests/**: 测试代码
- **setup.sh** 和 **setup.ps1**: 跨平台安装脚本
- **requirements*.txt**: 各种依赖项定义文件

## 核心安装流程

安装 Freqtrade 的标准流程包括以下步骤：
1. 确保系统已安装 Python 3.11 或更高版本。
2. 克隆 Freqtrade 仓库。
3. 使用 `setup.sh`（Linux/macOS）或 `setup.ps1`（Windows）脚本自动创建虚拟环境并安装依赖。
4. 激活虚拟环境。
5. 验证安装。

## setup.sh 脚本详解（Linux/macOS）

`setup.sh` 是为 Linux 和 macOS 用户设计的 Bash 脚本，用于自动化安装过程。

### 主要功能
- **Python 版本检测**：脚本会自动检测系统中是否存在 Python 3.11、3.12 或 3.13，并优先使用。
- **虚拟环境创建**：使用 `python -m venv .venv` 创建名为 `.venv` 的虚拟环境。
- **依赖项选择性安装**：
  - **开发依赖**：询问是否安装 `requirements-dev.txt`（包含所有其他依赖）。
  - **绘图依赖**：若未选择开发依赖，则单独询问是否安装 `requirements-plot.txt`。
  - **Hyperopt 依赖**：询问是否安装 `requirements-hyperopt.txt`（Raspberry Pi 等 ARM 设备会跳过此步骤）。
  - **FreqAI 依赖**：询问是否安装 `requirements-freqai.txt`，并可进一步选择安装 `requirements-freqai-rl.txt`（包含 PyTorch 等大型库）。
- **主程序安装**：使用 `pip install -e .` 以可编辑模式安装 Freqtrade。
- **freqUI 安装**：自动执行 `freqtrade install-ui` 命令。

### 使用方法
```bash
# 克隆仓库
git clone https://github.com/freqtrade/freqtrade.git
cd freqtrade

# 运行安装脚本
./setup.sh -i
```
运行 `./setup.sh` 时，脚本会通过交互式提示引导用户完成安装。

**Section sources**
- [setup.sh](file://setup.sh#L0-L290)

## setup.ps1 脚本详解（Windows）

`setup.ps1` 是为 Windows 用户设计的 PowerShell 脚本，功能与 `setup.sh` 类似。

### 主要功能
- **Python 可执行文件查找**：脚本会按优先级顺序搜索多个可能的 Python 安装路径（如 `python`, `python3.13`, `python3.12`, `python3.11` 以及常见的 Windows 安装路径）。
- **虚拟环境管理**：检查 `.venv` 目录，若不存在则创建；若存在则激活。
- **日志记录**：将所有操作记录到 `%TEMP%` 目录下的时间戳日志文件中，便于故障排查。
- **依赖项选择**：以字母选项（A, B, C...）的形式列出所有 `requirements` 文件，用户可选择一个或多个进行安装。
- **主程序与 freqUI 安装**：在虚拟环境中执行 `pip install -e .` 和 `python freqtrade install-ui`。

### 使用方法
1. 以管理员身份打开 PowerShell。
2. 导航到 Freqtrade 项目目录。
3. 执行脚本：
   ```powershell
   .\setup.ps1
   ```
   脚本会自动处理后续步骤。

**Section sources**
- [setup.ps1](file://setup.ps1#L0-L272)

## requirements 文件功能解析

Freqtrade 使用多个 `requirements.txt` 文件来管理不同场景下的依赖关系。

### 主要文件及其区别

| requirements 文件 | 功能描述 | 依赖关系 |
| :--- | :--- | :--- |
| **requirements.txt** | **核心依赖**：运行 Freqtrade 所需的最基本库，包括 `numpy`, `pandas`, `ccxt`, `SQLAlchemy`, `fastapi` 等。 | 基础 |
| **requirements-dev.txt** | **开发依赖**：包含所有其他 `requirements` 文件的完整依赖集，用于开发和测试。 | `-r requirements.txt`<br>`-r requirements-plot.txt`<br>`-r requirements-hyperopt.txt`<br>`-r requirements-freqai.txt`<br>`-r requirements-freqai-rl.txt` |
| **requirements-hyperopt.txt** | **超参数优化依赖**：支持 `hyperopt` 命令所需的库，如 `scipy`, `scikit-learn`, `optuna`。 | `-r requirements.txt` |
| **requirements-plot.txt** | **绘图依赖**：支持 `plot-dataframe` 和 `plot-profit` 命令所需的 `plotly` 库。 | `-r requirements.txt` |
| **requirements-freqai.txt** | **FreqAI 依赖**：支持机器学习预测模型（FreqAI）的基础库，如 `scikit-learn`, `catboost`, `lightgbm`, `xgboost`。 | `-r requirements.txt`<br>`-r requirements-plot.txt` |
| **requirements-freqai-rl.txt** | **FreqAI-RL 依赖**：在 `requirements-freqai.txt` 基础上，增加了强化学习支持库，如 `torch` (PyTorch), `stable_baselines3`。 | `-r requirements-freqai.txt` |

**Section sources**
- [requirements.txt](file://requirements.txt#L0-L63)
- [requirements-dev.txt](file://requirements-dev.txt#L0-L32)
- [requirements-hyperopt.txt](file://requirements-hyperopt.txt#L0-L9)
- [requirements-plot.txt](file://requirements-plot.txt#L0-L4)
- [requirements-freqai.txt](file://requirements-freqai.txt#L0-L12)
- [requirements-freqai-rl.txt](file://requirements-freqai-rl.txt#L0-L11)

## 虚拟环境管理与激活

虚拟环境是隔离项目依赖的关键，避免与系统或其他项目产生冲突。

### 激活命令
- **Linux/macOS**:
  ```bash
  source .venv/bin/activate
  ```
- **Windows**:
  ```cmd
  .venv\Scripts\activate
  ```
  或在 PowerShell 中：
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

激活后，命令行提示符前会显示 `(.venv)`，表示已进入虚拟环境。

**Section sources**
- [setup.sh](file://setup.sh#L48)
- [setup.sh](file://setup.sh#L154)
- [setup.sh](file://setup.sh#L247)

## 常见问题与解决方案

### 权限错误
- **问题**：在 Linux/macOS 上运行 `setup.sh` 时提示权限不足。
- **解决方案**：为脚本添加执行权限。
  ```bash
  chmod +x setup.sh
  ```

### 依赖冲突
- **问题**：`pip` 安装时出现版本冲突。
- **解决方案**：
  1. 确保在干净的虚拟环境中安装。
  2. 使用 `setup.sh` 或 `setup.ps1` 脚本，它们会处理依赖关系。
  3. 手动安装时，先升级 `pip`：
     ```bash
     pip install --upgrade pip
     ```

### Python 版本错误
- **问题**：脚本提示未找到 Python 3.11+。
- **解决方案**：
  - **Linux/macOS**: 使用 `pyenv` 或包管理器安装指定版本。
  - **Windows**: 从 [python.org](https://www.python.org/downloads/) 下载并安装 Python 3.11+，并确保其路径已添加到系统 `PATH` 环境变量中。

### Git Pull 失败
- **问题**：`setup.ps1` 在执行 `git pull` 时失败。
- **解决方案**：如果本地有未提交的更改，脚本会跳过 `git pull`。可手动执行 `git stash` 保存更改，或 `git reset --hard` 丢弃更改后重试。

## 验证安装

安装完成后，可通过以下命令验证：

```bash
# 激活虚拟环境 (Linux/macOS)
source .venv/bin/activate

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 查看 Freqtrade 版本
freqtrade --version

# 查看所有可用命令
freqtrade --help
```
如果能正确显示版本号和帮助信息，则表示安装成功。

**Section sources**
- [setup.sh](file://setup.sh#L249)

## 总结

本文档详细介绍了通过 `setup.sh` 和 `setup.ps1` 脚本使用 pip 安装 Freqtrade 的完整流程。通过理解不同 `requirements` 文件的作用，用户可以根据需求选择性安装组件，从而高效地搭建 Freqtrade 交易机器人环境。遵循本文指南，可以避免常见的安装问题，确保系统稳定运行。