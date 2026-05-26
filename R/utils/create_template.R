# 创建无编号标题的Word模板

library(officer)

# 创建空白文档
doc <- read_docx()

# 添加说明
doc <- body_add_par(doc, "此模板的Heading样式已设置为无自动编号", style = "Normal")
doc <- body_add_par(doc, "请在Word中手动设置：", style = "Normal")
doc <- body_add_par(doc, "1. 右键点击'标题1'样式 -> 修改", style = "Normal")
doc <- body_add_par(doc, "2. 点击'格式' -> '编号' -> 选择'无'", style = "Normal")
doc <- body_add_par(doc, "3. 对'标题2'重复相同操作", style = "Normal")
doc <- body_add_par(doc, "4. 保存为template.docx", style = "Normal")

# 保存模板
print(doc, target = "template_base.docx")

cat("已生成template_base.docx，请按说明手动设置后另存为template.docx\n")
