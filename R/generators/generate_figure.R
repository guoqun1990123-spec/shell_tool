# 图形生成模块

#' 创建KM曲线图
#' @param dataset 生存数据，需包含：time（时间）、status（事件状态0/1）、group（分组）
#' @param title 图标题
#' @param xlab X轴标签
#' @param ylab Y轴标签
#' @return 图片文件路径
create_kmplot <- function(dataset, title = "Kaplan-Meier曲线",
                         xlab = "时间（月）", ylab = "生存率") {

  require(survival)
  require(survminer)
  require(ggplot2)

  # 拟合生存曲线
  fit <- survfit(Surv(time, status) ~ group, data = dataset)

  # 绘制KM曲线
  p <- ggsurvplot(
    fit,
    data = dataset,
    pval = TRUE,
    conf.int = TRUE,
    risk.table = TRUE,
    xlab = xlab,
    ylab = ylab,
    title = title,
    font.main = c(14, "bold"),
    font.x = c(12, "plain"),
    font.y = c(12, "plain"),
    font.tickslab = c(10, "plain"),
    legend.title = "组别",
    legend.labs = unique(dataset$group)
  )

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p$plot, width = 8, height = 6, dpi = 300)

  return(temp_file)
}

#' 创建游泳图
#' @param dataset 数据，需包含：subject（受试者ID）、start（开始时间）、end（结束时间）、event（事件类型）、response（应答状态，可选）
#' @param title 图标题
#' @param xlab X轴标签
#' @return 图片文件路径
create_swimplot <- function(dataset, title = "治疗持续时间游泳图",
                           xlab = "时间（周）") {

  require(ggplot2)

  # 基础游泳图
  p <- ggplot(dataset, aes(x = start, xend = end, y = subject, yend = subject)) +
    geom_segment(aes(color = event), size = 3) +
    labs(title = title, x = xlab, y = "受试者", color = "事件") +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text = element_text(size = 10),
      axis.title = element_text(size = 12),
      legend.position = "bottom"
    )

  # 如果有应答状态，添加标记点
  if ("response" %in% colnames(dataset)) {
    response_data <- dataset[!is.na(dataset$response), ]
    if (nrow(response_data) > 0) {
      p <- p + geom_point(data = response_data, aes(x = end, y = subject, shape = response), size = 4)
    }
  }

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p, width = 10, height = 6, dpi = 300)

  return(temp_file)
}

#' 创建瀑布图
#' @param dataset 数据，需包含：subject（受试者ID）、change（变化值）、response（应答状态，可选）
#' @param title 图标题
#' @param ylab Y轴标签
#' @return 图片文件路径
create_waterfallplot <- function(dataset, title = "肿瘤最佳变化瀑布图",
                                 ylab = "肿瘤负荷变化 (%)") {

  require(ggplot2)

  # 按变化值排序
  dataset <- dataset[order(dataset$change), ]
  dataset$subject <- factor(dataset$subject, levels = dataset$subject)

  # 基础瀑布图
  p <- ggplot(dataset, aes(x = subject, y = change)) +
    geom_bar(stat = "identity", aes(fill = change > 0), width = 0.8) +
    scale_fill_manual(values = c("TRUE" = "#d73027", "FALSE" = "#4575b4"),
                     labels = c("TRUE" = "进展", "FALSE" = "缓解"),
                     name = "") +
    labs(title = title, x = "受试者", y = ylab) +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text.x = element_text(angle = 90, hjust = 1, size = 8),
      axis.text.y = element_text(size = 10),
      axis.title = element_text(size = 12),
      legend.position = "bottom"
    ) +
    geom_hline(yintercept = 0, linetype = "solid", color = "black")

  # 如果有应答状态，添加标记
  if ("response" %in% colnames(dataset)) {
    response_data <- dataset[!is.na(dataset$response), ]
    if (nrow(response_data) > 0) {
      p <- p + geom_point(data = response_data, aes(x = subject, y = change, shape = response), size = 3)
    }
  }

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p, width = 10, height = 6, dpi = 300)

  return(temp_file)
}

#' 创建蜘蛛图
#' @param dataset 数据，需包含：subject（受试者ID）、time（时间点）、value（测量值）
#' @param title 图标题
#' @param xlab X轴标签
#' @param ylab Y轴标签
#' @return 图片文件路径
create_spiderplot <- function(dataset, title = "肿瘤负荷变化蜘蛛图",
                              xlab = "时间（周）", ylab = "肿瘤负荷变化 (%)") {

  require(ggplot2)

  # 蜘蛛图
  p <- ggplot(dataset, aes(x = time, y = value, group = subject, color = subject)) +
    geom_line(linewidth = 0.8, alpha = 0.7) +
    geom_point(size = 2) +
    labs(title = title, x = xlab, y = ylab) +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text = element_text(size = 10),
      axis.title = element_text(size = 12),
      legend.position = "none"
    ) +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50")

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p, width = 10, height = 6, dpi = 300)

  return(temp_file)
}

#' 创建折线图
#' @param dataset 数据，需包含：time（时间点）、value（测量值）、group（分组）
#' @param title 图标题
#' @param xlab X轴标签
#' @param ylab Y轴标签
#' @return 图片文件路径
create_seriesplot <- function(dataset, title = "时间序列折线图",
                              xlab = "时间", ylab = "测量值") {

  require(ggplot2)

  # 折线图
  p <- ggplot(dataset, aes(x = time, y = value, group = group, color = group)) +
    geom_line(linewidth = 1.2) +
    geom_point(size = 3) +
    labs(title = title, x = xlab, y = ylab, color = "组别") +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text = element_text(size = 10),
      axis.title = element_text(size = 12),
      legend.position = "bottom"
    )

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p, width = 10, height = 6, dpi = 300)

  return(temp_file)
}

#' 创建森林图
#' @param dataset 数据，需包含：subgroup（亚组）、hr（风险比）、lower（95%CI下限）、upper（95%CI上限）
#' @param title 图标题
#' @return 图片文件路径
create_forestplot <- function(dataset, title = "亚组分析森林图") {

  require(ggplot2)

  # 反转亚组顺序，使第一个在顶部
  dataset$subgroup <- factor(dataset$subgroup, levels = rev(dataset$subgroup))

  # 森林图
  p <- ggplot(dataset, aes(x = hr, y = subgroup)) +
    geom_vline(xintercept = 1, linetype = "dashed", color = "gray50") +
    geom_errorbarh(aes(xmin = lower, xmax = upper), height = 0.2, linewidth = 0.8) +
    geom_point(size = 4, shape = 18) +
    labs(title = title, x = "风险比 (95% CI)", y = "") +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text = element_text(size = 10),
      axis.title = element_text(size = 12)
    ) +
    scale_x_continuous(breaks = seq(0, 3, 0.5))

  # 保存为临时文件
  temp_file <- tempfile(fileext = ".png")
  ggsave(temp_file, plot = p, width = 10, height = 6, dpi = 300)

  return(temp_file)
}
