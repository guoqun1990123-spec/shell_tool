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
    parsed   <- read_yaml_input(config_file)
    config   <- parsed$config
    datasets <- parsed$datasets
    figures  <- if (!is.null(parsed$figures)) parsed$figures else list()
  } else {
    config   <- read_config(config_file)
    datasets <- read_datasets(datasets_file)
    figures  <- list()   # Excel 输入路径暂不支持嵌入图片
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
  # 记录生成失败的条目，用于汇总
  failed_items <- c()

  # 遍历每个TFL
  for (i in 1:nrow(config)) {
    row <- config[i, ]
    cat(sprintf("生成 [%s] %s...\n", row$SeqNum, row$`table no`))

    # tryCatch 容错：单条出错只插红色占位，不中断整份文档生成
    doc <- tryCatch({
      # 根据MacVar类型生成内容
      if (is.na(row$MacVar) || row$MacVar == "") {
        cat("  跳过：MacVar为空\n")
        doc  # 不做任何操作，返回当前 doc
      } else if (row$MacVar == "PStab") {
        add_table_to_doc(doc, row, datasets, displayed_sections)
      } else if (row$MacVar == "RptList") {
        add_listing_to_doc(doc, row, datasets, displayed_sections)
      } else if (row$MacVar == "mtext") {
        add_mtext_to_doc(doc, row, config, datasets, displayed_sections)
      } else if (tolower(row$MacVar) %in% c("kmplot", "forestplot", "swimplot",
                                             "waterfallplot", "spiderplot", "seriesplot")) {
        add_figure_to_doc(doc, row, datasets, figures, displayed_sections)
      } else {
        cat(sprintf("  跳过未知类型: %s\n", row$MacVar))
        doc  # 不做任何操作，返回当前 doc
      }
    }, error = function(e) {
      # 打印错误供排查（不抑制），插红色占位后继续
      msg <- conditionMessage(e)
      cat(sprintf("  ！生成失败（SeqNum=%s，%s）：%s\n",
                  row$SeqNum, row$`table no`, msg))
      failed_items <<- c(failed_items,
                         sprintf("[%s] %s", row$`table no`, row$title))
      add_error_placeholder(doc, row, msg)
    })

    # 更新已显示章节（成功/占位均更新，保持章节标题去重逻辑正常）
    section_no <- row$`Section no`
    if (!is.null(section_no) && length(section_no) > 0 && !is.na(section_no)) {
      displayed_sections <- c(displayed_sections, section_no)
    }
  }

  # 汇总失败条目
  if (length(failed_items) > 0) {
    cat(sprintf("\n⚠ 共 %d 条生成失败，已用红色占位替代：\n", length(failed_items)))
    for (item in failed_items) cat(sprintf("  - %s\n", item))
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
# generate_figure.R（mock 合成图）已不再使用，改为 assemble 侧插入文字占位框
source("R/assemble_document.R")
