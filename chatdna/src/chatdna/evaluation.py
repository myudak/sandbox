"""Local generation proxies; no prompts, targets or generated strings in reports."""
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
import random
import re
from statistics import mean
from .runtime import save_json,records,seed_all
from .inference import LocalModels
from .data import normalize

def repeat_rate(text):
    tokens=normalize(text).split()
    grams=[tuple(tokens[i:i+3]) for i in range(len(tokens)-2)]
    return 0 if not grams else 1-len(set(grams))/len(grams)

def compare(registry,dataset,output,samples=12,seed=42,split='test',temperature=0):
    rng=random.Random(seed)
    heldout=[]
    for i,record in enumerate(records(Path(dataset)/f'sft_{split}.jsonl')):
        if len(heldout)<samples:
            heldout.append(record)
        else:
            choice=rng.randrange(i+1)
            if choice<samples:
                heldout[choice]=record
    models=LocalModels(registry)
    report={'protocol':{'generation_context':'Last incoming turn from genuinely held-out direct conversations; not the full multi-turn context. Scratch receives this text as a continuation prefix, so conversation scores are exploratory.','seed':seed,'samples':len(heldout),'max_new_tokens':32,'decoding':'greedy','privacy':'No prompts, targets or generations saved; aggregate overlap and suppression only.','interpretation':'Character overlap is not a semantic relevance score. Human style/relevance judgement and blinded preference remain unmeasured.'},'models':{}}
    report['protocol'].update(split=split,decoding='greedy' if temperature==0 else f'sampling temperature={temperature}; HF top_p=0.8, top_k=20; scratch top_k=40')
    for item in models.listing():
        if not item['available']:
            report['models'][item['id']]={'available':False}
            continue
        models.load(item['id'])
        seed_all(seed)
        scores=[]; repeats=[]; lengths=[]; times=[]; suppressed=0; slang=0; empty=0
        for sample in heldout:
            incoming=next(m['content'] for m in reversed(sample['messages'][:-1]) if m['role']=='user')
            result=models.generate(item['id'],incoming,temperature=temperature,max_new_tokens=32)
            if result.get('empty_output'):
                empty+=1
                scores.append(0.0)
                repeats.append(0.0)
            elif result['suppressed']:
                suppressed+=1
            else:
                text=result['text']
                scores.append(SequenceMatcher(None,normalize(sample['messages'][-1]['content']),normalize(text)).ratio())
                repeats.append(repeat_rate(text))
                slang+=int(bool(re.search(r'(?i)wkwk|anjir|jir\b|haha',text)))
            lengths.append(result['output_tokens']); times.append(result['seconds'])
        probes=[('Jawab angka saja: 2 + 2 =','4'),('Complete with one word: one, two,','three'),('Translate the Indonesian greeting halo to English. One word.','hello')]
        correct=0
        for prompt,expected in probes:
            response=models.generate(item['id'],prompt,temperature=temperature,max_new_tokens=16)
            correct+=int(not response['suppressed'] and bool(re.search(r'\b'+re.escape(expected)+r'\b',response['text'],re.I)))
        report['models'][item['id']]={'available':True,'mean_character_overlap_unsuppressed':mean(scores) if scores else None,'mean_repeated_trigram_rate_unsuppressed':mean(repeats) if repeats else None,'mean_output_tokens':mean(lengths),'mean_generation_seconds':mean(times),'training_overlap_or_privacy_suppressed':suppressed,'empty_outputs':empty,'slang_marker_responses_unsuppressed':slang,'synthetic_general_probes_correct':correct,'synthetic_general_probes_total':len(probes),'subjective_style_and_semantic_relevance':'Not measured; requires human review'}
        models.unload()
    save_json(output,report)
    return report

def scratch_continuations(registry,dataset,output,samples=12,seed=42):
    models=LocalModels(registry)
    eligible=[]; rng=random.Random(seed); seen=0
    for record in records(Path(dataset)/'lm_validation.jsonl'):
        if len(record['text'].split())<4:
            continue
        seen+=1
        if len(eligible)<samples:
            eligible.append(record['text'])
        else:
            j=rng.randrange(seen)
            if j<samples:
                eligible[j]=record['text']
    models.load('scratch')
    report={'protocol':'Owner-text validation continuations, first two words as prefix; no private strings saved. Not a chatbot relevance test.','samples':len(eligible),'decoding':{}}
    for temperature in (0,.8):
        seed_all(seed)
        nonempty=suppressed=tokens=characters=0
        for text in eligible:
            result=models.generate('scratch',' '.join(text.split()[:2]),temperature=temperature,max_new_tokens=32)
            nonempty+=int(not result['empty_output'] and not result['suppressed'])
            suppressed+=int(result['suppressed'])
            tokens+=result['output_tokens']
            if not result['suppressed'] and not result['empty_output']:
                characters+=len(result['text'])
        report['decoding'][str(temperature)]={'nonempty_outputs':nonempty,'privacy_suppressed':suppressed,'mean_output_tokens':tokens/len(eligible),'mean_clean_characters':characters/len(eligible)}
    models.unload()
    save_json(output,report)
    return report
