"""Polish the existing manuscript, retaining the frozen experimental evidence."""
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]


def prepare():
    path=ROOT/'paper/main.tex'
    backup=ROOT/'deliverables/snapshots/paper_before_release_2026-10-31.tex'
    if not backup.exists():shutil.copy2(path,backup)
    source=path.read_text(encoding='utf-8')
    preamble=r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=25mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,microtype}
\usepackage{amsmath,amssymb,booktabs,graphicx,array,longtable}
\usepackage{xcolor,xurl,caption,fancyhdr}
\usepackage[section]{placeins}
\usepackage{hyperref}
\definecolor{paperlink}{RGB}{24,60,91}
\hypersetup{colorlinks=true,urlcolor=paperlink,citecolor=paperlink,linkcolor=paperlink,
 pdftitle={Separating Training Exposure from Data Scarcity in MuSGD-YOLO Fine-Tuning under Missing Annotations},
 pdfauthor={Muchammad Yuda Tri Ananda},
 pdfsubject={Empirical object detection optimizer comparison with fixed image exposure},
 pdfkeywords={object detection, MuSGD, YOLO26, missing annotations, data scarcity}}
\captionsetup{font=small,labelfont=bf}
\setlength{\emergencystretch}{2em}
\setlength{\parskip}{0.2em}
\setlength{\textfloatsep}{14pt plus 3pt minus 3pt}
\renewcommand{\arraystretch}{1.12}
\widowpenalty=10000
\clubpenalty=10000
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small MuSGD--YOLO fine-tuning}
\fancyhead[R]{\small M.\,Y.\,T.\ Ananda}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\setlength{\headheight}{14pt}
"""
    title=source.index(r'\title{')
    source=preamble+source[title:]
    source=source.replace(r'\author{Author information to be supplied}',r'\author{Muchammad Yuda Tri Ananda\\[3pt]\normalsize\href{mailto:yuda@myudak.com}{\texttt{yuda@myudak.com}}}')
    source=source.replace(r'\date{31 October 2026 --- results draft}',r'\date{31 October 2026}')
    source=re.sub(r'\\draftnote\{[^\n]*\}\n','',source)
    source=source.replace(r'\maketitle',r'\maketitle'+'\n'+r'\thispagestyle{plain}',1)
    source=source.replace(r'\end{abstract}',r'\end{abstract}'+'\n'+r'\noindent\textbf{Keywords:} object detection; MuSGD; YOLO26; missing annotations; data scarcity; fixed exposure.'+'\n',1)
    source=source.replace('The candidate contribution is a controlled account of how the recipe difference changes with image availability and missing training annotations, while distinguishing unique-image availability from repeated image exposure.',
        'We quantify how recipe differences vary with available images and missing training annotations while holding presented-image exposure and update count constant.')
    source=source.replace('A positive result, a null result, and a reversal after controlling exposure are all admissible outcomes. No directional hypothesis was fixed before the pilot; the journal protocol was developed after observing it.',
        'The protocol was developed after the pilot, and no directional hypothesis was preregistered. The later randomized blocks provide separate evidence for the fixed-exposure comparison.')
    start=source.index(r'\section{Related work}')
    end=source.index(r'\section{Methods}')
    related=r"""\section{Related work}
Muon applies orthogonalized matrix updates \cite{jordan2024}. Ultralytics YOLO26 combines Muon and SGD updates in its MuSGD training recipe \cite{jocher2026}; MiMuon is another mixed optimizer with detector experiments \cite{huang2026}. Matrix-based updates in object detection are therefore established. Our comparison concerns the existing library recipes during fine-tuning, with controlled image availability and training-box deletion.

Budget definitions affect optimizer comparisons. Akhtar et al.\ distinguish matched-data, elapsed-time and tuning-budget evaluations \cite{akhtar2026}. Here, primary cells receive equal image presentations and updates, while timings include the surrounding training and validation pipeline. Equal candidate counts constrain the search budget but do not ensure equally complete search coverage.

Ruan et al.\ study input-corruption robustness and feature transfer \cite{ruan2026}. The present intervention instead removes training annotations while retaining the original images. Fine-tuning also depends on checkpoint lineage: Qu et al.\ investigate switching from Adam pretraining to Muon \cite{qu2026}. Our fixed YOLO26 checkpoint records MuSGD pretraining, so an Adam-pretraining mismatch explanation does not directly apply.

Missing-box learning is an established positive--unlabeled detection problem \cite{yang2020}. Annotation-incompleteness studies further distinguish controlled synthetic deletion from natural omissions and ambiguous labels \cite{penquitt2026}. We evaluate unchanged retained source annotations, with independent deletion applied only to training labels. The resulting VOC-derived metric is explicitly separate from standard VOC evaluation \cite{everingham2010}.

"""
    source=source[:start]+related+source[end:]
    source=source.replace('The original African Wildlife download contains','The African Wildlife download \\cite{wildlifeData} contains',1)
    source=source.replace('The external task uses the official VOC2007 train, validation and test membership','The external task uses the official VOC2007 train, validation and test membership \\cite{everingham2010}',1)
    source=source.replace('Full original test membership is retained. Image licensing and possible overlap with pretraining data remain unresolved.',
        'Full original test membership is retained. Dataset terms remain those of the original providers; possible overlap with pretraining data is not excluded.')
    source=source.replace('Report block values, means, standard deviations and approximate Student $t$ intervals across independent joint blocks.',
        'We report means and approximate Student $t$ intervals across independent joint blocks; the accompanying evidence retains block values and standard deviations.')
    pilot_start=source.index(r'\section{Development pilot results}')
    pilot_end=source.index(r'\section{Journal campaign results}')
    pilot=source[pilot_start:pilot_end]
    figure_start=pilot.find(r'\IfFileExists{images/pilot_validation_trajectories.png}')
    if figure_start!=-1:pilot=pilot[:figure_start]
    pilot=pilot.replace(r'\section{Development pilot results}',r'\section{Development pilot}',1)
    source=source[:pilot_start]+source[pilot_end:]
    source=source.replace(r'\section{Journal campaign results}',r'\section{Results}',1)
    source=source.replace(r'\textbf{Every selected learning rate is the lowest searched value.}',
        'The selected learning rate for every optimizer is the lower boundary of its grid.')
    source=source.replace('This observation should not be omitted in favor of a MuSGD-centered narrative.',
        'SGD therefore remains a competitive comparator in the evaluated setting.')
    source=source.replace(r'\IfFileExists{test_means.tex}{\input{test_means.tex}}{}',r'\input{test_means.tex}')
    source=source.replace(r'\IfFileExists{images/journal_test_contrasts.png}{','')
    source=source.replace(r'\end{figure}}{}',r'\end{figure}')
    begin=source.index(r'\subsection{Full paired summaries}')
    end=source.index(r'\section{Discussion and limitations}')
    source=source[:begin]+source[end:]
    source=source.replace('Dataset rights must be resolved before redistributing photographs.',
        'Source photographs are not included in the manuscript or companion source bundle.')
    begin=source.index(r'\section{Reproducibility and availability}')
    end=source.index(r'\section{Conclusion}')
    availability=r"""\section{Code and data availability}
The public Kaggle notebook is available at
\url{https://www.kaggle.com/code/myudak/muon-yolo-journal}.
The completed experimental run and its outputs are preserved in version~1:
\url{https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=361947826}.
Later visibility or presentation saves do not replace that evidence.

The notebook embeds source, tests and frozen configuration with integrity checks. Its outputs include source and variant fingerprints, checkpoint lineage, an environment lock, optimizer groups, actual update counts, image-order hashes, histories, metric records and the final checkpoint freeze. Principal evidence files are \texttt{results.json}, \texttt{campaign\_summary.json}, \texttt{frozen\_final\_test\_plan.json}, and \texttt{final\_test\_results.json}, under \texttt{muon\_yolo\_journal/}. The compact evidence audit verifies recorded identities and internal consistency; independent rehashing of source-image and checkpoint bytes requires those larger artifacts.

African Wildlife and VOC images remain third-party data subject to their source terms \cite{wildlifeData,everingham2010}. The paper contains numerical figures rather than source photographs. Upstream software and model licenses retain their own terms.

"""
    source=source[:begin]+availability+source[end:]
    ref_start=source.index(r'\begin{thebibliography}')
    source=source[:ref_start]+r'\appendix'+'\n'+pilot+'\n'+r'\section{Complete paired estimates}'+'\n'+r'\input{journal_results.tex}'+'\n\n'+source[ref_start:]
    source=source.replace(r'\begin{thebibliography}{9}',r'\begin{thebibliography}{99}')
    extra=r"""\bibitem{ruan2026} T. Ruan, F. Zhang, S. Wang and S. Zhang. \emph{Muon Learns More Robust and Transferable Features than Adam}. arXiv:2606.09658, 2026. \url{https://arxiv.org/abs/2606.09658}.
\bibitem{qu2026} X. Qu, H. Peigeng and S. Horv\'ath. \emph{Can Muon Fine-tune Adam-Pretrained Models?} Proceedings of the 43rd International Conference on Machine Learning, PMLR 306:102619--102650, 2026. \url{https://proceedings.mlr.press/v306/qu26e.html}.
\bibitem{penquitt2026} S. Penquitt et al. \emph{Object Detection Benchmarks are Incomplete: The Role of Label Errors and Annotation Uncertainty}. arXiv:2609.21822, 2026. \url{https://arxiv.org/abs/2609.21822}.
\bibitem{everingham2010} M. Everingham, L. Van Gool, C. K. I. Williams, J. Winn and A. Zisserman. \emph{The Pascal Visual Object Classes (VOC) Challenge}. International Journal of Computer Vision, 88:303--338, 2010. \url{https://doi.org/10.1007/s11263-009-0275-4}.
\bibitem{wildlifeData} Ultralytics. \emph{African Wildlife Detection Dataset}. Dataset documentation, accessed 31 October 2026. \url{https://docs.ultralytics.com/datasets/detect/african-wildlife/}.
"""
    source=source.replace(r'\end{thebibliography}',extra+r'\end{thebibliography}')
    assert not any(word in source for word in ('draftnote','Author information to be supplied','still being finalized','results draft'))
    path.write_text(source,encoding='utf-8',newline='\n')
    summary=json.loads((ROOT/'outputs/kaggle_journal_v1/muon_yolo_journal/campaign_summary.json').read_text())
    lines=[r'All estimates below use joint blocks 101--103. Differences and approximate unadjusted 95\% Student $t$ intervals are in AP points. The three-way contrast follows the definition in the main text.']
    for split,split_title in (('validation','Validation'),('frozen_test','Frozen test')):
        for dataset,group in summary[split].items():
            name='African Wildlife' if dataset=='wildlife' else 'VOC2007-derived'
            lines += [r'\subsection{'+name+': '+split_title.lower()+r'}',
                r'\begin{longtable}{@{}lrrrr@{}}',
                r'\caption{'+name+': '+split_title.lower()+r' paired recipe differences.}\\',
                r'\toprule Recipe versus AdamW & Images & Missing & Mean & 95\% interval\\\midrule',
                r'\endfirsthead',r'\toprule Recipe versus AdamW & Images & Missing & Mean & 95\% interval\\\midrule',r'\endhead']
            for row in group['paired_optimizer_contrasts']:
                lo,hi=row['ci95'];recipe=row['contrast'].split(' minus ')[0]
                lines.append(f"{recipe} & {row['fraction']:.0%} & {row['missing_probability']:.0%} & {row['mean']:+.2f} & [{lo:.2f}, {hi:.2f}]".replace('%',r'\%')+r'\\')
            lines += [r'\bottomrule\end{longtable}']
            for row in group['three_way_interactions']:
                recipe=row['contrast'].split(' minus ')[0];lo,hi=row['ci95']
                lines.append(f"{recipe}--AdamW three-way contrast: "+'$'+f"{row['mean']:+.3f}"+'$ AP points; approximate 95'+r'\% interval '+f"$[{lo:.3f}, {hi:.3f}]$.")
    (ROOT/'paper/journal_results.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print('Polished the existing paper/main.tex and regenerated paired-estimate appendix.')


if __name__=='__main__':prepare()
