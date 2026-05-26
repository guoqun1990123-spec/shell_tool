# 添加游泳图配置到config.xlsx

library(openxlsx)

# 读取现有config
config_file <- "config/config.xlsx"
config <- read.xlsx(config_file, sheet = 1)

# 创建新行（使用实际的列名）
new_row <- data.frame(
  Section.no = "14.3",
  Section.title = "安全性分析",
  table.no = "图14.3.2",
  title = "治疗持续时间游泳图",
  pop = "FAS",
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
  Datesets = "swimplot",
  MacVar = "Swimplot",
  RfeTFL = NA,
  SeqNum = 10,
  Adcols = NA,
  Varlab = NA,
  Labparm = NA,
  Trtlab = NA,
  Subgrop = NA,
  ByseqL = NA,
  stringsAsFactors = FALSE
)

# 添加到config
config <- rbind(config, new_row)

# 保存
write.xlsx(config, "config/config.xlsx", overwrite = TRUE)

cat("已添加游泳图配置到config.xlsx\n")
cat("SeqNum: 10, MacVar: Swimplot, Datasets: swimplot\n")
