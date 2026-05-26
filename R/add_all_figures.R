# 添加所有图形类型的示例数据和配置

library(openxlsx)

# 读取现有文件
datasets_file <- "config/datasets.xlsx"
config_file <- "config/config.xlsx"

wb_data <- loadWorkbook(datasets_file)
config <- read.xlsx(config_file, sheet = 1)

# 1. 瀑布图数据
waterfall_data <- data.frame(
  subject = paste0("S", sprintf("%03d", 1:30)),
  change = c(seq(-80, -20, length.out = 15), seq(5, 60, length.out = 15)),
  response = sample(c("CR", "PR", "SD", "PD", NA), 30, replace = TRUE, prob = c(0.15, 0.25, 0.35, 0.15, 0.1))
)

if (!"waterfallplot" %in% names(wb_data)) {
  addWorksheet(wb_data, "waterfallplot")
}
writeData(wb_data, "waterfallplot", waterfall_data)

# 2. 蜘蛛图数据
spider_data <- data.frame(
  subject = rep(paste0("S", sprintf("%03d", 1:15)), each = 5),
  time = rep(c(0, 4, 8, 12, 16), 15),
  value = c(sapply(1:15, function(i) {
    baseline <- 0
    trend <- rnorm(1, -5, 10)
    cumsum(c(baseline, rnorm(4, trend, 15)))
  }))
)

if (!"spiderplot" %in% names(wb_data)) {
  addWorksheet(wb_data, "spiderplot")
}
writeData(wb_data, "spiderplot", spider_data)

# 3. 折线图数据
series_data <- data.frame(
  time = rep(c(0, 2, 4, 6, 8, 12, 16, 20, 24), 2),
  value = c(
    c(100, 95, 88, 82, 78, 70, 65, 62, 60),  # 治疗组
    c(100, 98, 95, 90, 85, 78, 70, 65, 58)   # 对照组
  ),
  group = rep(c("IMM01联合阿扎胞苷", "安慰剂联合阿扎胞苷"), each = 9)
)

if (!"seriesplot" %in% names(wb_data)) {
  addWorksheet(wb_data, "seriesplot")
}
writeData(wb_data, "seriesplot", series_data)

# 4. 森林图数据
forest_data <- data.frame(
  subgroup = c("总体", "年龄<65岁", "年龄≥65岁", "男性", "女性", "ECOG 0-1", "ECOG 2"),
  hr = c(0.75, 0.68, 0.82, 0.73, 0.78, 0.70, 0.85),
  lower = c(0.60, 0.48, 0.62, 0.55, 0.58, 0.52, 0.63),
  upper = c(0.95, 0.95, 1.08, 0.97, 1.05, 0.94, 1.15)
)

if (!"forestplot" %in% names(wb_data)) {
  addWorksheet(wb_data, "forestplot")
}
writeData(wb_data, "forestplot", forest_data)

# 保存datasets
saveWorkbook(wb_data, "config/datasets.xlsx", overwrite = TRUE)

# 添加配置
new_configs <- data.frame(
  Section.no = c("14.4", "14.4", "14.4", "14.4"),
  Section.title = c("疗效分析", "疗效分析", "疗效分析", "疗效分析"),
  table.no = c("图14.4.1", "图14.4.2", "图14.4.3", "图14.4.4"),
  title = c("肿瘤最佳变化瀑布图", "肿瘤负荷变化蜘蛛图", "肿瘤负荷时间序列图", "亚组分析森林图"),
  pop = c("FAS", "FAS", "FAS", "FAS"),
  footnote1 = NA,
  footnote2 = NA,
  footnote3 = NA,
  footnote4 = NA,
  footnote5 = NA,
  footnote6 = NA,
  footnote7 = NA,
  Dutoffdate = NA,
  Source_data = NA,
  PgmNote = NA,
  Datesets = c("waterfallplot", "spiderplot", "seriesplot", "forestplot"),
  MacVar = c("WaterfallPlot", "Spiderplot", "Seriesplot", "Forestplot"),
  RfeTFL = NA,
  SeqNum = 11:14,
  Adcols = NA,
  Varlab = NA,
  Labparm = NA,
  Trtlab = NA,
  Subgrop = NA,
  ByseqL = NA,
  stringsAsFactors = FALSE
)

config <- rbind(config, new_configs)
write.xlsx(config, "config/config.xlsx", overwrite = TRUE)

cat("已添加所有图形数据和配置:\n")
cat("- 瀑布图 (WaterfallPlot): waterfallplot\n")
cat("- 蜘蛛图 (Spiderplot): spiderplot\n")
cat("- 折线图 (Seriesplot): seriesplot\n")
cat("- 森林图 (Forestplot): forestplot\n")
