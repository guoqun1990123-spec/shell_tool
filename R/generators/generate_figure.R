# 图形生成模块

# ── 共享辅助函数 ──────────────────────────────────────────────────────────────

#' 解析轴标签："x|y" → c(x, y)，空段落用默认值
.fig_axis_labels <- function(varlab, default_x, default_y) {
  if (is.null(varlab) || is.na(varlab) || !nzchar(trimws(varlab)))
    return(c(default_x, default_y))
  parts <- trimws(strsplit(varlab, "\\|")[[1]])
  c(if (length(parts) >= 1 && nzchar(parts[1])) parts[1] else default_x,
    if (length(parts) >= 2 && nzchar(parts[2])) parts[2] else default_y)
}

#' 解析图例标签：Trtlab → 字符向量；空则 NULL（由调用方回退到数据推断）
.fig_legend_labs <- function(trtlab) {
  if (is.null(trtlab) || is.na(trtlab) || !nzchar(trimws(trtlab))) return(NULL)
  trimws(strsplit(trtlab, "\\|")[[1]])
}

#' 加"示意图"水印：右上角灰字 + 底部 caption
.fig_add_watermark <- function(p) {
  p +
    ggplot2::annotate("text", x = Inf, y = Inf, label = "示意图",
                      hjust = 1.1, vjust = 1.4, size = 6,
                      color = "grey75", fontface = "italic") +
    ggplot2::labs(caption = "示意图：数据为模拟示例，非真实分析结果")
}

#' 统一出图：8×6 in / 300 dpi，与 Word 插入尺寸 6×4.5（4:3）对齐，杜绝变形
#' @param is_ggsurv ggsurvplot 对象需用 png+print 方式以保留 risk.table
.fig_save <- function(plot_obj, is_ggsurv = FALSE) {
  temp_file <- tempfile(fileext = ".png")
  if (is_ggsurv) {
    png(temp_file, width = 8, height = 6, units = "in", res = 300)
    print(plot_obj)
    dev.off()
  } else {
    ggplot2::ggsave(temp_file, plot = plot_obj, width = 8, height = 6, dpi = 300)
  }
  temp_file
}

# ── KM 曲线图 ─────────────────────────────────────────────────────────────────

#' 创建KM曲线图（Shell 阶段输出示意图）
#' @param dataset 生存数据，需包含：time（时间）、status（事件状态0/1）、group（分组）；
#'   缺少必需列时自动使用内置示例数据。
#' @param title  图标题（来自 config$title）
#' @param xlab   X轴标签（来自 Varlab 解析，或默认"时间（月）"）
#' @param ylab   Y轴标签（来自 Varlab 解析，或默认"生存率"）
#' @param legend_labs 图例文字向量（来自 Trtlab 解析）；NULL 则由数据推断
#' @return 临时 PNG 文件路径
create_kmplot <- function(dataset,
                          title       = "Kaplan-Meier曲线",
                          xlab        = "时间（月）",
                          ylab        = "生存率",
                          legend_labs = NULL) {

  require(survival)
  require(survminer)
  require(ggplot2)

  # 缺少必需列时使用内置示例数据（Shell 占位场景）
  if (!all(c("time", "status", "group") %in% names(dataset))) {
    dataset <- data.frame(
      time   = c(2, 4, 6, 8, 10, 12, 3, 5, 7, 9, 11, 13),
      status = c(1, 1, 0, 1,  0,  1, 1, 0, 1, 1,  0,  1),
      group  = rep(c("试验组", "对照组"), each = 6)
    )
  }

  # 确定图例文字：优先用 Trtlab，回退到数据
  legs <- if (!is.null(legend_labs) && length(legend_labs) > 0) {
    legend_labs
  } else {
    unique(dataset$group)
  }

  # 拟合并绘图
  fit <- survfit(Surv(time, status) ~ group, data = dataset)

  p <- ggsurvplot(
    fit,
    data         = dataset,
    pval         = TRUE,
    conf.int     = TRUE,
    risk.table   = TRUE,
    xlab         = xlab,
    ylab         = ylab,
    title        = title,
    legend.title = "组别",
    legend.labs  = legs,
    font.main    = c(14, "bold"),
    font.x       = c(12, "plain"),
    font.y       = c(12, "plain"),
    font.tickslab = c(10, "plain")
  )

  # 水印加在主图层
  p$plot <- .fig_add_watermark(p$plot)

  return(.fig_save(p, is_ggsurv = TRUE))
}

# ── 游泳图 ────────────────────────────────────────────────────────────────────

#' 创建游泳图（Shell 阶段输出示意图）
#' @param dataset 数据，需包含：subject、start、end、event；response 可选
#' @param title   图标题
#' @param xlab    X轴标签
#' @param ylab    Y轴标签（游泳图 y 轴为受试者，一般无需改动）
#' @param legend_labs 未使用，保留以统一签名
#' @return 临时 PNG 文件路径
create_swimplot <- function(dataset,
                            title       = "治疗持续时间游泳图",
                            xlab        = "时间（周）",
                            ylab        = "受试者",
                            legend_labs = NULL) {

  require(ggplot2)

  # 缺少必需列时使用内置示例数据
  if (!all(c("subject", "start", "end", "event") %in% names(dataset))) {
    dataset <- data.frame(
      subject  = paste0("S", sprintf("%02d", 1:10)),
      start    = rep(0, 10),
      end      = c(12, 8, 20, 6, 16, 10, 24, 4, 18, 14),
      event    = rep(c("治疗中", "完成"), 5),
      response = c("PR", NA, "CR", NA, "PR", NA, "SD", NA, "PR", NA)
    )
  }

  p <- ggplot(dataset, aes(x = start, xend = end, y = subject, yend = subject)) +
    geom_segment(aes(color = event), linewidth = 3) +
    labs(title = title, x = xlab, y = ylab, color = "状态") +
    theme_minimal() +
    theme(
      plot.title   = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text    = element_text(size = 10),
      axis.title   = element_text(size = 12),
      legend.position = "bottom"
    )

  if ("response" %in% colnames(dataset)) {
    response_data <- dataset[!is.na(dataset$response), ]
    if (nrow(response_data) > 0) {
      p <- p + geom_point(data = response_data,
                          aes(x = end, y = subject, shape = response), size = 4)
    }
  }

  p <- .fig_add_watermark(p)
  return(.fig_save(p))
}

# ── 瀑布图 ────────────────────────────────────────────────────────────────────

#' 创建瀑布图（Shell 阶段输出示意图）
#' @param dataset 数据，需包含：subject、change；response 可选
#' @param title   图标题
#' @param xlab    X轴标签
#' @param ylab    Y轴标签
#' @param legend_labs 未使用，保留以统一签名
#' @return 临时 PNG 文件路径
create_waterfallplot <- function(dataset,
                                 title       = "肿瘤最佳变化瀑布图",
                                 xlab        = "受试者",
                                 ylab        = "肿瘤负荷变化 (%)",
                                 legend_labs = NULL) {

  require(ggplot2)

  # 缺少必需列时使用内置示例数据
  if (!all(c("subject", "change") %in% names(dataset))) {
    dataset <- data.frame(
      subject  = paste0("S", sprintf("%03d", 1:20)),
      change   = c(seq(-80, -10, length.out = 12), seq(5, 50, length.out = 8)),
      response = c(rep(c("CR", "PR"), 6), rep(c("SD", "PD"), 4))
    )
  }

  dataset <- dataset[order(dataset$change), ]
  dataset$subject <- factor(dataset$subject, levels = dataset$subject)

  p <- ggplot(dataset, aes(x = subject, y = change)) +
    geom_bar(stat = "identity", aes(fill = change > 0), width = 0.8) +
    scale_fill_manual(
      values = c("TRUE" = "#d73027", "FALSE" = "#4575b4"),
      labels = c("TRUE" = "进展", "FALSE" = "缓解"),
      name   = ""
    ) +
    labs(title = title, x = xlab, y = ylab) +
    theme_minimal() +
    theme(
      plot.title    = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text.x   = element_text(angle = 90, hjust = 1, size = 8),
      axis.text.y   = element_text(size = 10),
      axis.title    = element_text(size = 12),
      legend.position = "bottom"
    ) +
    geom_hline(yintercept = 0, linetype = "solid", color = "black")

  if ("response" %in% colnames(dataset)) {
    response_data <- dataset[!is.na(dataset$response), ]
    if (nrow(response_data) > 0) {
      p <- p + geom_point(data = response_data,
                          aes(x = subject, y = change, shape = response), size = 3)
    }
  }

  p <- .fig_add_watermark(p)
  return(.fig_save(p))
}

# ── 蜘蛛图 ────────────────────────────────────────────────────────────────────

#' 创建蜘蛛图（Shell 阶段输出示意图）
#' @param dataset 数据，需包含：subject、time、value
#' @param title   图标题
#' @param xlab    X轴标签
#' @param ylab    Y轴标签
#' @param legend_labs 未使用，保留以统一签名
#' @return 临时 PNG 文件路径
create_spiderplot <- function(dataset,
                               title       = "肿瘤负荷变化蜘蛛图",
                               xlab        = "时间（周）",
                               ylab        = "肿瘤负荷变化 (%)",
                               legend_labs = NULL) {

  require(ggplot2)

  # 缺少必需列时使用内置示例数据
  if (!all(c("subject", "time", "value") %in% names(dataset))) {
    dataset <- data.frame(
      subject = rep(paste0("S", sprintf("%02d", 1:8)), each = 5),
      time    = rep(c(0, 4, 8, 12, 16), 8),
      value   = c(-5, -20, -35, -42, -40,
                   0,  -8, -15, -10,  -5,
                  -2, -18, -30, -25, -20,
                   0,   5,  15,  25,  30,
                  -8, -25, -45, -50, -48,
                  -3, -10, -20, -18, -15,
                   5,  10,  20,  35,  40,
                  -1,  -5, -12, -10,  -8)
    )
  }

  p <- ggplot(dataset, aes(x = time, y = value, group = subject, color = subject)) +
    geom_line(linewidth = 0.8, alpha = 0.7) +
    geom_point(size = 2) +
    labs(title = title, x = xlab, y = ylab) +
    theme_minimal() +
    theme(
      plot.title      = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text       = element_text(size = 10),
      axis.title      = element_text(size = 12),
      legend.position = "none"
    ) +
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray50")

  p <- .fig_add_watermark(p)
  return(.fig_save(p))
}

# ── 折线图 ────────────────────────────────────────────────────────────────────

#' 创建时间序列折线图（Shell 阶段输出示意图）
#' @param dataset 数据，需包含：time、value、group
#' @param title   图标题
#' @param xlab    X轴标签
#' @param ylab    Y轴标签
#' @param legend_labs 图例文字向量（来自 Trtlab 解析）；NULL 则由数据推断
#' @return 临时 PNG 文件路径
create_seriesplot <- function(dataset,
                               title       = "时间序列折线图",
                               xlab        = "时间",
                               ylab        = "测量值",
                               legend_labs = NULL) {

  require(ggplot2)

  # 缺少必需列时使用内置示例数据
  if (!all(c("time", "value", "group") %in% names(dataset))) {
    dataset <- data.frame(
      time  = rep(c(0, 2, 4, 6, 8, 12, 16, 20, 24), 2),
      value = c(100, 95, 88, 82, 78, 70, 65, 62, 60,
                100, 98, 95, 90, 85, 78, 70, 65, 58),
      group = rep(c("试验组", "对照组"), each = 9)
    )
  }

  # 图例文字：优先用 Trtlab，回退到数据
  legs <- if (!is.null(legend_labs) && length(legend_labs) > 0) {
    # 重命名 group 因子水平
    grp_levels <- unique(dataset$group)
    if (length(legs <- legend_labs) == length(grp_levels)) {
      dataset$group <- factor(dataset$group, levels = grp_levels, labels = legs)
    }
    legs
  } else {
    unique(as.character(dataset$group))
  }

  p <- ggplot(dataset, aes(x = time, y = value, group = group, color = group)) +
    geom_line(linewidth = 1.2) +
    geom_point(size = 3) +
    labs(title = title, x = xlab, y = ylab, color = "组别") +
    theme_minimal() +
    theme(
      plot.title      = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text       = element_text(size = 10),
      axis.title      = element_text(size = 12),
      legend.position = "bottom"
    )

  p <- .fig_add_watermark(p)
  return(.fig_save(p))
}

# ── 森林图 ────────────────────────────────────────────────────────────────────

#' 创建亚组分析森林图（Shell 阶段输出示意图）
#' @param dataset 数据，需包含：subgroup、hr、lower、upper
#' @param title   图标题
#' @param xlab    X轴标签
#' @param ylab    Y轴标签（森林图 y 轴为亚组，一般无需改动）
#' @param legend_labs 未使用，保留以统一签名
#' @return 临时 PNG 文件路径
create_forestplot <- function(dataset,
                               title       = "亚组分析森林图",
                               xlab        = "风险比 (95% CI)",
                               ylab        = "",
                               legend_labs = NULL) {

  require(ggplot2)

  # 缺少必需列时使用内置示例数据
  if (!all(c("subgroup", "hr", "lower", "upper") %in% names(dataset))) {
    dataset <- data.frame(
      subgroup = c("总体", "年龄<65岁", "年龄≥65岁", "男性", "女性", "ECOG 0-1", "ECOG 2"),
      hr       = c(0.75, 0.68, 0.82, 0.73, 0.78, 0.70, 0.85),
      lower    = c(0.60, 0.48, 0.62, 0.55, 0.58, 0.52, 0.63),
      upper    = c(0.95, 0.95, 1.08, 0.97, 1.05, 0.94, 1.15)
    )
  }

  dataset$subgroup <- factor(dataset$subgroup, levels = rev(dataset$subgroup))

  p <- ggplot(dataset, aes(x = hr, y = subgroup)) +
    geom_vline(xintercept = 1, linetype = "dashed", color = "gray50") +
    geom_errorbarh(aes(xmin = lower, xmax = upper), height = 0.2, linewidth = 0.8) +
    geom_point(size = 4, shape = 18) +
    labs(title = title, x = xlab, y = ylab) +
    theme_minimal() +
    theme(
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      axis.text  = element_text(size = 10),
      axis.title = element_text(size = 12)
    ) +
    scale_x_continuous(breaks = seq(0, 3, 0.5))

  p <- .fig_add_watermark(p)
  return(.fig_save(p))
}
