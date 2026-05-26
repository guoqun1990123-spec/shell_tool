# 创建示例生存数据

library(openxlsx)

# 读取现有datasets
datasets_file <- "datasets.xlsx"
wb <- loadWorkbook(datasets_file)

# 创建生存数据
set.seed(123)
n <- 100

surv_data <- data.frame(
  time = c(
    # 治疗组：生存时间较长
    round(rexp(50, rate = 0.05), 1),
    # 对照组：生存时间较短
    round(rexp(50, rate = 0.08), 1)
  ),
  status = c(
    # 治疗组：事件发生率较低
    rbinom(50, 1, 0.6),
    # 对照组：事件发生率较高
    rbinom(50, 1, 0.75)
  ),
  group = c(
    rep("IMM01联合阿扎胞苷", 50),
    rep("安慰剂联合阿扎胞苷", 50)
  )
)

# 添加工作表
addWorksheet(wb, "survival")
writeData(wb, "survival", surv_data)

# 保存
saveWorkbook(wb, datasets_file, overwrite = TRUE)

cat("已添加survival工作表到datasets.xlsx\n")
cat("包含", nrow(surv_data), "条生存数据记录\n")
