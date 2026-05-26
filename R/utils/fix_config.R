# 修复config.xlsx，添加ByseqL列和SeqNum

library(openxlsx)

# 读取config
config <- read.xlsx("config.xlsx", sheet = 1)

# 添加ByseqL列
if (!"ByseqL" %in% colnames(config)) {
  config$ByseqL <- NA
}

# 设置清单的ByseqL和SeqNum
if (nrow(config) >= 7) {
  config$ByseqL[7] <- 1401
  if (is.na(config$SeqNum[7])) {
    config$SeqNum[7] <- 7
  }
}

if (nrow(config) >= 8) {
  config$ByseqL[8] <- 1402
  if (is.na(config$SeqNum[8])) {
    config$SeqNum[8] <- 8
  }
}

# 保存回文件
write.xlsx(config, "config.xlsx", overwrite = TRUE)
cat("已修复config.xlsx：\n")
cat("  - 第7行：ByseqL=1401, SeqNum=7\n")
cat("  - 第8行：ByseqL=1402, SeqNum=8\n")


