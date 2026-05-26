# 示例运行脚本

# 安装依赖（首次运行时取消注释）
# install.packages(c("openxlsx", "officer", "flextable", "dplyr",
#                    "survival", "survminer", "ggplot2", "ggpubr", "yaml"))

# 设置工作目录
setwd("d:/shell_tool")

# 加载主函数
source("R/generators/generate_shell.R")

# 定义文件路径
# config_file <- "config/config_ISS.xlsx"
# datasets_file <- "config/datasets_ISS.xlsx"
# output_file <- "output/output_shell_ISS.docx"


config_file <- "config/config_sample.xlsx"
datasets_file <- "config/datasets_sample.xlsx"
output_file <- "output/output_shell_sample.docx"


# 生成Shell文档（Excel输入）
generate_shell(
  config_file = config_file,
  datasets_file = datasets_file,
  output_file = output_file
)

# --- YAML输入示例（Web界面生成后自动提交Git，供本地调用） ---
# generate_shell(
#   config_file  = "config/config_sample.yaml",  # datasets_file 可省略
#   datasets_file = NULL,
#   output_file  = "output/output_shell_yaml.docx"
# )
