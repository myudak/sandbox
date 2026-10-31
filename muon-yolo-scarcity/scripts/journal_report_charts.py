"""Pure presentation of archived numeric evidence; contains no training code."""
import csv
import html
import io
import json
import math
import statistics
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
from IPython.display import HTML, IFrame, display

COLORS={'AdamW':'#64748b','MuSGD':'#2563eb','SGD':'#059669'}
NAMES={'wildlife':'African Wildlife','voc2007':'VOC2007-derived'}
SPLITS={'frozen_test':'Frozen test','validation':'Validation'}
CONDITIONS=[(0.2,0.0),(0.2,0.2),(1.0,0.0),(1.0,0.2)]
CONFIG={'displaylogo':False,'responsive':True,'toImageButtonOptions':{'format':'svg'}}
FIGURES={}
pio.templates.default='plotly_white'


def condition(f,q):
    return f'{f:.0%} images / {q:.0%} missing boxes'


def style(fig,title,ytitle=None,height=520):
    fig.update_layout(title={'text':title,'x':0.01,'font':{'size':21}},height=height,
        font={'family':'Arial, sans-serif','size':13,'color':'#24334b'},
        margin={'l':165,'r':35,'t':135,'b':75},paper_bgcolor='white',plot_bgcolor='white',
        legend={'orientation':'h','y':-0.18,'x':0},hoverlabel={'bgcolor':'white'},
        xaxis={'gridcolor':'#e8edf4','zerolinecolor':'#94a3b8'},
        yaxis={'gridcolor':'#e8edf4','title':ytitle})
    return fig


def menu(buttons,x=0):
    return {'buttons':buttons,'direction':'down','x':x,'y':1.20,'xanchor':'left',
        'yanchor':'top','showactive':True,'bgcolor':'#f1f5f9','bordercolor':'#cbd5e1'}


def show(name,fig):
    FIGURES[name]=fig
    # Kaggle's RequireJS can interfere with the connected Plotly renderer.
    # Isolate each chart in its own HTML document with a shared local JS bundle.
    on_kaggle=Path('/kaggle/working').exists()
    output=Path('/kaggle/working') if on_kaggle else Path('output/kaggle_report')
    output.mkdir(parents=True,exist_ok=True)
    fig.write_html(output/(name+'.html'),include_plotlyjs='directory',full_html=True,
        config=CONFIG,div_id=name)
    src=name+'.html' if on_kaggle else '../../output/kaggle_report/'+name+'.html'
    display(IFrame(src=src,width='100%',height=fig.layout.height+24))


def effects(snapshot):
    fig=go.Figure();groups=[]
    for split in ('frozen_test','validation'):
        for dataset in NAMES:
            indices=[]
            for optimizer,offset in [('MuSGD',-0.10),('SGD',0.10)]:
                records=[r for r in snapshot['summary'][split][dataset]['paired_optimizer_contrasts']
                         if r['contrast']==f'{optimizer} minus AdamW']
                if not records:continue
                y=[CONDITIONS.index((r['fraction'],r['missing_probability']))+offset for r in records]
                indices.append(len(fig.data))
                fig.add_trace(go.Scatter(x=[r['mean'] for r in records],y=y,mode='markers',
                    name=f'{optimizer} minus AdamW',marker={'size':12,'color':COLORS[optimizer],
                    'symbol':'circle' if optimizer=='MuSGD' else 'diamond'},visible=False,
                    customdata=[[condition(r['fraction'],r['missing_probability']),*r['ci95']] for r in records],
                    error_x={'type':'data','array':[r['ci95'][1]-r['mean'] for r in records],
                    'arrayminus':[r['mean']-r['ci95'][0] for r in records],'color':COLORS[optimizer],'thickness':2},
                    hovertemplate='%{customdata[0]}<br>Mean: %{x:+.3f} AP points<br>Approx. 95% interval: [%{customdata[1]:.3f}, %{customdata[2]:.3f}]<extra>%{fullData.name}</extra>'))
                indices.append(len(fig.data))
                fig.add_trace(go.Scatter(x=[v for r in records for v in r['values']],
                    y=[yi for yi in y for _ in range(3)],mode='markers',showlegend=False,visible=False,
                    marker={'size':6,'opacity':0.4,'color':COLORS[optimizer]},
                    customdata=[[b,condition(r['fraction'],r['missing_probability'])] for r in records for b in (101,102,103)],
                    hovertemplate='%{customdata[1]}<br>Joint block %{customdata[0]}: %{x:+.3f} AP points<extra>Paired block difference</extra>'))
            groups.append((f'{NAMES[dataset]} · {SPLITS[split]}',indices))
    for i in groups[0][1]:fig.data[i].visible=True
    buttons=[{'label':label,'method':'update','args':[{'visible':[i in indices for i in range(len(fig.data))]},
        {'title.text':f'Recipe differences · {label}'}]} for label,indices in groups]
    style(fig,'Recipe differences · '+groups[0][0],height=560)
    fig.update_layout(updatemenus=[menu(buttons)],xaxis_title='mAP50–95 difference (AP points); positive favors the named recipe',
        yaxis={'tickvals':list(range(4)),'ticktext':[condition(*c) for c in CONDITIONS],'autorange':'reversed'})
    fig.add_vline(x=0,line_dash='dash',line_color='#475569')
    return fig


def scores(snapshot):
    fig=go.Figure();groups=[]
    for split in ('frozen_test','validation'):
        for dataset in NAMES:
            indices=[]
            for optimizer in COLORS:
                rows=[r for r in snapshot['summary'][split][dataset]['conditions'] if r['optimizer']==optimizer]
                if not rows:continue
                indices.append(len(fig.data))
                fig.add_trace(go.Bar(name=optimizer,x=[f"{r['fraction']:.0%} images<br>{r['missing_probability']:.0%} missing boxes" for r in rows],
                    y=[r['mean'] for r in rows],marker_color=COLORS[optimizer],visible=False,
                    error_y={'type':'data','array':[r['ci95'][1]-r['mean'] for r in rows],
                        'arrayminus':[r['mean']-r['ci95'][0] for r in rows]},
                    text=[f"{r['mean']:.2f}" for r in rows],textposition='outside',
                    hovertemplate='%{x}<br>Mean mAP50–95: %{y:.3f} AP<extra>%{fullData.name}</extra>'))
            groups.append((f'{NAMES[dataset]} · {SPLITS[split]}',indices))
    for i in groups[0][1]:fig.data[i].visible=True
    buttons=[{'label':label,'method':'update','args':[{'visible':[i in indices for i in range(len(fig.data))]},
        {'title.text':'Absolute scores · '+label}]} for label,indices in groups]
    style(fig,'Absolute scores · '+groups[0][0],'mAP50–95 × 100 (AP)',height=565)
    fig.update_layout(barmode='group',margin_l=65,updatemenus=[menu(buttons)],yaxis_range=[0,100],xaxis_tickangle=0)
    return fig


def interaction(snapshot):
    fig=go.Figure();groups=[]
    for split in ('frozen_test','validation'):
        indices=[];labels=[];records=[]
        for dataset in NAMES:
            for row in snapshot['summary'][split][dataset]['three_way_interactions']:
                labels.append(NAMES[dataset]+'<br>'+row['contrast'].split(':')[0].replace(' minus ',' − '));records.append(row)
        indices.append(len(fig.data))
        fig.add_trace(go.Scatter(x=[r['mean'] for r in records],y=labels,mode='markers',visible=False,
            marker={'size':12,'color':'#7c3aed'},name='Three-way interaction',
            error_x={'type':'data','array':[r['ci95'][1]-r['mean'] for r in records],
                'arrayminus':[r['mean']-r['ci95'][0] for r in records]},
            customdata=[r['ci95'] for r in records],
            hovertemplate='%{y}<br>Interaction: %{x:+.3f} AP points<br>Approx. 95% interval: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<extra></extra>'))
        groups.append((SPLITS[split],indices))
    fig.data[0].visible=True
    buttons=[{'label':label,'method':'update','args':[{'visible':[i in indices for i in range(len(fig.data))]},
        {'title.text':'Scarcity × missingness interaction · '+label}]} for label,indices in groups]
    style(fig,'Scarcity × missingness interaction · Frozen test',height=440)
    fig.update_layout(margin_l=175,updatemenus=[menu(buttons)],showlegend=False,
        xaxis_title='Difference of paired recipe differences (AP points)',yaxis_autorange='reversed')
    fig.add_vline(x=0,line_dash='dash',line_color='#475569')
    return fig


def search(snapshot):
    fig=go.Figure();groups=[]
    for optimizer in COLORS:
        indices=[]
        rows=snapshot['selection']['diagnostics'][optimizer]['ranked']
        for decay in (0.0,0.0005):
            selected=sorted([r for r in rows if r['hyperparameters']['weight_decay']==decay],key=lambda r:r['hyperparameters']['lr0'])
            indices.append(len(fig.data))
            fig.add_trace(go.Scatter(x=[r['hyperparameters']['lr0'] for r in selected],
                y=[100*r['mean_anchor_val_map'] for r in selected],mode='lines+markers',visible=False,
                name=f'Weight decay {decay:g}',line={'color':COLORS[optimizer],'dash':'solid' if decay else 'dot'},
                marker={'size':10,'symbol':'circle' if decay else 'diamond'},
                hovertemplate='Base learning rate: %{x:g}<br>Mean anchor validation AP: %{y:.3f}<extra>%{fullData.name}</extra>'))
        best=rows[0];indices.append(len(fig.data))
        fig.add_trace(go.Scatter(x=[best['hyperparameters']['lr0']],y=[100*best['mean_anchor_val_map']],
            mode='markers',name='Selected candidate',visible=False,marker={'size':19,'symbol':'star','color':'#e59b20'},
            hovertemplate='Selected at the lower LR boundary<br>LR %{x:g} · validation AP %{y:.3f}<extra></extra>'))
        groups.append((optimizer,indices))
    for i in groups[0][1]:fig.data[i].visible=True
    style(fig,'Validation search · AdamW','Mean two-anchor validation mAP50–95 × 100',height=515)
    fig.update_layout(margin_l=80,xaxis_type='log',xaxis_title='Base learning rate (log scale)',yaxis_range=[0,100],
        updatemenus=[menu([{'label':label,'method':'update','args':[{'visible':[i in ids for i in range(len(fig.data))]},
            {'title.text':'Validation search · '+label}]} for label,ids in groups])])
    return fig


def curves(snapshot):
    fig=go.Figure();groups=[];ap=[];loss=[]
    for dataset in NAMES:
        for fraction,missing in CONDITIONS:
            indices=[]
            records=[r for r in snapshot['histories'] if r['dataset']==dataset and r['fraction']==fraction and r['missing']==missing]
            for row in sorted(records,key=lambda r:(r['optimizer'],r['block'])):
                indices.append(len(fig.data));ap.append(row['ap']);loss.append(row['box_loss'])
                fig.add_trace(go.Scatter(x=row['exposure'],y=row['ap'],mode='lines',visible=False,
                    name=f"{row['optimizer']} · block {row['block']}",
                    line={'color':COLORS[row['optimizer']],'dash':{101:'solid',102:'dot',103:'dash'}[row['block']],'width':2},
                    hovertemplate='Presented images: %{x:,}<br>Value: %{y:.3f}<extra>%{fullData.name}</extra>'))
            groups.append((NAMES[dataset]+' · '+condition(fraction,missing),indices))
    for i in groups[0][1]:fig.data[i].visible=True
    style(fig,'Learning trajectories','Clean validation mAP50–95 × 100',height=610)
    fig.update_layout(margin_l=80,xaxis_title='Actual image presentations (not unique images)',legend_y=-0.20,
        updatemenus=[menu([{'label':label,'method':'update','args':[{'visible':[i in ids for i in range(len(fig.data))]},
            {'title.text':'Learning trajectories'}]} for label,ids in groups]),
            menu([{'label':'Validation AP','method':'update','args':[{'y':ap},{'yaxis.title.text':'Clean validation mAP50–95 × 100'}]},
                  {'label':'Training box loss','method':'update','args':[{'y':loss},{'yaxis.title.text':'Training box loss'}]}],x=0.72)])
    return fig


def table(rows):
    columns=list(rows[0])
    return '<div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%"><thead><tr>'+''.join(
        '<th style="text-align:left;padding:9px;border-bottom:2px solid #cbd5e1">'+html.escape(k)+'</th>' for k in columns
    )+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td style="padding:9px;border-bottom:1px solid #e2e8f0">'+html.escape(str(r[k]))+'</td>' for k in columns)+'</tr>' for r in rows)+'</tbody></table></div>'


def exact_table(snapshot):
    rows=[]
    for dataset in NAMES:
        group=snapshot['summary']['frozen_test'][dataset]
        for f,q in CONDITIONS:
            values={r['optimizer']:r['mean'] for r in group['conditions'] if (r['fraction'],r['missing_probability'])==(f,q)}
            difference=next(r for r in group['paired_optimizer_contrasts'] if r['contrast']=='MuSGD minus AdamW' and (r['fraction'],r['missing_probability'])==(f,q))
            rows.append({'Dataset':NAMES[dataset],'Images':f'{f:.0%}','Missing':f'{q:.0%}',
                'AdamW':f"{values['AdamW']:.2f}",'MuSGD':f"{values['MuSGD']:.2f}",
                'SGD':f"{values['SGD']:.2f}" if 'SGD' in values else 'Not evaluated',
                'MuSGD − AdamW':f"{difference['mean']:+.2f}",
                'Approx. 95% paired interval':f"[{difference['ci95'][0]:.2f}, {difference['ci95'][1]:.2f}]"})
    return table(rows)


def save_outputs(snapshot,sections):
    output=Path('/kaggle/working') if Path('/kaggle/working').exists() else Path('output/kaggle_report')
    output.mkdir(parents=True,exist_ok=True)
    (output/'reviewed_evidence.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    with (output/'trial_metrics.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(snapshot['trials'][0]));writer.writeheader();writer.writerows(snapshot['trials'])
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MuSGD × YOLO26 — Results Explorer</title>',
        '<style>body{font:16px/1.65 system-ui,sans-serif;color:#24334b;margin:0;background:#f1f5f9}main{max-width:1120px;margin:auto;padding:48px 30px;background:white}h1{font-size:38px;line-height:1.2}h2{margin-top:54px}a{color:#2563eb}.note{padding:20px;background:#eff6ff;border-left:4px solid #2563eb}.plotly-graph-div{max-width:100%}td,th{font-size:14px}code{font-size:13px;overflow-wrap:anywhere}</style><main>']
    first=True
    for heading,body,chart in sections:
        parts.append(f'<h2>{heading}</h2>' if heading else '')
        parts.append(body)
        if chart:
            parts.append(FIGURES[chart].to_html(full_html=False,include_plotlyjs=True if first else False,config=CONFIG,div_id=chart))
            first=False
    parts.append('</main></html>')
    (output/'muon_yolo_results_explorer.html').write_text('\n'.join(parts),encoding='utf-8')
    (output/'figure_specs.json').write_text(json.dumps({k:json.loads(f.to_json()) for k,f in FIGURES.items()}),encoding='utf-8')
    return output
