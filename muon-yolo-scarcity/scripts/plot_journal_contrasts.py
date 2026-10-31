"""Export a scientific figure of paired frozen-test contrasts and uncertainty."""
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'outputs/kaggle_journal_v1/muon_yolo_journal/campaign_summary.json'
    summary=json.loads(source.read_text())
    plt.rcParams.update({'font.size':11,'axes.titlesize':12,'axes.labelsize':11})
    fig,axes=plt.subplots(2,1,figsize=(7.2,7.5),sharex=True,sharey=True)
    conditions=[(.2,0.),(.2,.2),(1.,0.),(1.,.2)]
    colors={'MuSGD minus AdamW':'#2166ac','SGD minus AdamW':'#1b9e77'}
    all_bounds=[]
    for ax,dataset,title in zip(axes,('wildlife','voc2007'),('African Wildlife','VOC2007-derived')):
        group=summary['frozen_test'][dataset]
        assert group['joint_blocks']==[101,102,103]
        for label,color in colors.items():
            records=[r for r in group['paired_optimizer_contrasts'] if r['contrast']==label]
            if not records:continue
            for i,(fraction,noise) in enumerate(conditions):
                row=next(r for r in records if (r['fraction'],r['missing_probability'])==(fraction,noise))
                mean=row['mean'];lo,hi=row['ci95'];all_bounds.extend((lo,hi))
                offset=(-.10 if label.startswith('MuSGD') else .10) if dataset=='wildlife' else 0
                y=i+offset
                ax.errorbar(mean,y,xerr=[[mean-lo],[hi-mean]],fmt='o',markersize=6,capsize=3,
                    color=color,label=label if i==0 else None,zorder=3)
                ax.scatter(row['values'],[y-.035,y,y+.035],s=15,alpha=.4,color=color,zorder=2)
        ax.axvline(0,color='#555555',linestyle='--',linewidth=1)
        ax.set_title(title+' (3 paired joint blocks)')
        ax.set_xlabel('Test mAP50–95 difference (AP points)')
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_yticks(range(4),['20% images / clean','20% images / 20% missing','100% images / clean','100% images / 20% missing'])
    axes[0].invert_yaxis()
    axes[0].set_xlim(min(all_bounds)-.6,max(all_bounds)+.6)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.945),ncol=2,frameon=False,fontsize=10)
    fig.suptitle('Frozen test: paired recipe differences',fontsize=14,y=1.0)
    fig.text(.5,.015,'Means and approximate 95% t intervals; small dots: joint-block differences.\nExploratory cell contrasts, without multiplicity adjustment.',ha='center',fontsize=9.5)
    fig.tight_layout(rect=(0,.055,1,.90))
    folder=ROOT/'research/figures';folder.mkdir(exist_ok=True)
    for suffix in ('png','svg'):fig.savefig(folder/f'journal_test_contrasts.{suffix}',dpi=200)
    plt.close(fig)
    shutil.copy2(folder/'journal_test_contrasts.png',ROOT/'paper/images/journal_test_contrasts.png')
    print(folder/'journal_test_contrasts.png')


if __name__=='__main__':main()
