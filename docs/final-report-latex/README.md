# Boring Financial LaTeX Final Report

这个目录包含期末项目报告的 LaTeX 源文件、配图和最终 PDF，章节结构依据老师提供的《最终报告提交要点》组织。

## 结构

```text
main.tex              主入口，负责封面、目录、全局格式和章节引用
chapters/*.tex        各章节正文
figures/              架构图、用例图、设计图和页面截图
tables/               可复用的独立表格文件
main.pdf              编译生成的最终提交版本
```

章节结构：

1. 可行性分析与规划
2. 需求分析
3. 用户界面与体验设计
4. 系统设计
5. 程序开发
6. 验收与发布
7. 运行与维护

## 编译

推荐使用 XeLaTeX：

```bash
cd docs/final-report-latex
xelatex main.tex
xelatex main.tex
```

也可以使用 latexmk：

```bash
latexmk -xelatex main.tex
```

提交前应至少连续编译两次，以刷新目录、图表编号和交叉引用。除 `main.pdf` 外，辅助文件均由本目录的 `.gitignore` 排除。
