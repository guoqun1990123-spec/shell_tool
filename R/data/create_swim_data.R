# 创建游泳图示例数据

library(openxlsx)

# 读取现有datasets
datasets_file <- "datasets.xlsx"
wb <- loadWorkbook(datasets_file)

# 创建游泳图数据
swim_data <- data.frame(
  subject = paste0("S", sprintf("%03d", 1:20)),
  start = rep(0, 20),
  end = c(12, 18, 24, 15, 30, 8, 22, 16, 28, 10,
          14, 20, 26, 12, 32, 6, 24, 18, 30, 14),
  event = sample(c("治疗中", "完成治疗", "中止治疗"), 20, replace = TRUE),
  response = sample(c("CR", "PR", "SD", "PD", NA), 20, replace = TRUE, prob = c(0.2, 0.3, 0.3, 0.1, 0.1))
)

# 添加工作表
addWorksheet(wb, "swimplot")
writeData(wb, "swimplot", swim_data)

# 保存
saveWorkbook(wb, datasets_file, overwrite = TRUE)

cat("已添加swimplot工作表到datasets.xlsx\n")
cat("包含", nrow(swim_data), "条游泳图数据记录\n")
