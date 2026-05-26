# 更新template.docx的字体样式

library(officer)

# 读取现有模板
doc <- read_docx("template.docx")

# 添加说明文字
doc <- body_add_par(doc, "请在Word中手动设置以下样式的字体：", style = "Normal")
doc <- body_add_par(doc, "1. 右键点击'正文'样式 -> 修改", style = "Normal")
doc <- body_add_par(doc, "2. 字体设置：中文字体=宋体，西文字体=Times New Roman，字号=五号(10.5磅)", style = "Normal")
doc <- body_add_par(doc, "3. 对'标题1'、'标题2'重复相同操作", style = "Normal")
doc <- body_add_par(doc, "4. 保存模板", style = "Normal")

# 保存
print(doc, target = "template_font_guide.docx")

cat("已生成template_font_guide.docx，请按说明手动设置字体后保存为template.docx\n")
