# Shell文档自动生成工具 - 主函数
# 作者: Auto-generated
# 日期: 2026-03-31

#' 生成Shell文档
#'
#' @param config_file config.xlsx文件路径
#' @param datasets_file datasets.xlsx文件路径
#' @param output_file 输出文件路径
#' @return 生成的文档路径
generate_shell <- function(config_file, datasets_file, output_file) {

  # 加载依赖包
  require(openxlsx)
  require(officer)
  require(dplyr)
  require(flextable)  # flextable最后加载，避免函数被覆盖

  # 读取配置和数据（支持 .xlsx 和 .yaml/.yml 两种输入格式）
  cat("读取配置文件...\n")
  ext <- tolower(tools::file_ext(config_file))
  if (ext %in% c("yaml", "yml")) {
    parsed <- read_yaml_input(config_file)
    config   <- parsed$config
    datasets <- parsed$datasets
  } else {
    config   <- read_config(config_file)
    datasets <- read_datasets(datasets_file)
  }

  # 初始化Word文档（使用无编号模板，继承页眉页脚）
  cat("初始化Word文档...\n")
  doc <- read_docx("templates/template.docx")

  # 注：不设置page_section，完全继承模板的页面设置（横向、页眉、页码）

  # 按SeqNum排序（NA值保持原顺序）
  config <- config[order(config$SeqNum, na.last = TRUE), ]

  # 添加目录
  doc <- body_add_par(doc, "目录", style = "heading 1")
  doc <- body_add_toc(doc, level = 2)
  doc <- body_add_break(doc)

  # 追踪已显示的章节
  displayed_sections <- c()

  # 遍历每个TFL
  for (i in 1:nrow(config)) {
    row <- config[i, ]
    cat(sprintf("生成 [%s] %s...\n", row$SeqNum, row$`table no`))

    # 根据MacVar类型生成内容
    if (is.na(row$MacVar) || row$MacVar == "") {
      cat("  跳过：MacVar为空\n")
    } else if (row$MacVar == "PStab") {
      doc <- add_table_to_doc(doc, row, datasets, displayed_sections)
      # 更新已显示章节
      section_no <- row$`Section no`
      if (!is.null(section_no) && length(section_no) > 0 && !is.na(section_no)) {
        displayed_sections <- c(displayed_sections, section_no)
      }
    } else if (row$MacVar == "RptList") {
      doc <- add_listing_to_doc(doc, row, datasets, displayed_sections)
      # 更新已显示章节
      section_no <- row$`Section no`
      if (!is.null(section_no) && length(section_no) > 0 && !is.na(section_no)) {
        displayed_sections <- c(displayed_sections, section_no)
      }
    } else if (row$MacVar == "mtext") {
      doc <- add_mtext_to_doc(doc, row, config, datasets, displayed_sections)
      # 更新已显示章节
      section_no <- row$`Section no`
      if (!is.null(section_no) && length(section_no) > 0 && !is.na(section_no)) {
        displayed_sections <- c(displayed_sections, section_no)
      }
    } else if (tolower(row$MacVar) %in% c("kmplot", "forestplot", "swimplot", "waterfallplot", "spiderplot", "seriesplot")) {
      doc <- add_figure_to_doc(doc, row, datasets, displayed_sections)
      # 更新已显示章节
      section_no <- row$`Section no`
      if (!is.null(section_no) && length(section_no) > 0 && !is.na(section_no)) {
        displayed_sections <- c(displayed_sections, section_no)
      }
    } else {
      cat(sprintf("  跳过未知类型: %s\n", row$MacVar))
    }
  }

  # 保存文档
  cat("保存文档...\n")
  print(doc, target = output_file)

  cat(sprintf("完成！文档已保存至: %s\n", output_file))
  return(output_file)
}

# 加载子模块
source("R/utils/read_config.R")
source("R/utils/read_yaml_config.R")
source("R/utils/parse_rich_text.R")
source("R/generators/generate_table.R")
source("R/generators/generate_listing.R")
source("R/generators/generate_figure.R")
source("R/assemble_document.R")
