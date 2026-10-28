"""Pure response-only tokenization, independent of model loading."""
from pathlib import Path
import random
from .runtime import records

def encode_response(tokenizer,messages,max_length=128):
    if not messages or messages[-1]['role']!='assistant':
        raise ValueError('Final message must be the owner target')
    context=[dict(m) for m in messages[:-1]]
    target=tokenizer.encode(messages[-1]['content'],add_special_tokens=False)+[tokenizer.eos_token_id]
    if len(target)>=max_length-16:
        return None
    while context:
        prefix=tokenizer.apply_chat_template(context,tokenize=True,add_generation_prompt=True,enable_thinking=False)
        if hasattr(prefix,'keys'):
            prefix=prefix['input_ids']
        if len(prefix)+len(target)<=max_length:
            ids=prefix+target
            labels=[-100]*len(prefix)+target
            assert all(t==-100 for t in labels[:len(prefix)])
            assert labels[len(prefix):]==target
            return {'input_ids':ids,'labels':labels,'attention_mask':[1]*len(ids),'target_tokens':len(target)}
        # Discard whole older turns. A long final user turn is skipped rather
        # than cutting through role delimiters or a private response target.
        if len(context)>1:
            context.pop(0)
            while context and context[0]['role']!='user':
                context.pop(0)
        else:
            return None
    return None

def load_samples(path,tokenizer,max_length=128,limit=5000,seed=42):
    rng=random.Random(seed)
    chosen=[]
    accepted=skipped=target_tokens=0
    lengths=[]
    for record in records(path):
        encoded=encode_response(tokenizer,record['messages'],max_length)
        if encoded is None:
            skipped+=1
            continue
        accepted+=1
        target_tokens+=encoded['target_tokens']
        lengths.append(len(encoded['input_ids']))
        if len(chosen)<limit:
            chosen.append(encoded)
        else:
            index=rng.randrange(accepted)
            if index<limit:
                chosen[index]=encoded
    if not chosen:
        raise ValueError('No response-only samples fit the configuration')
    import numpy as np
    return chosen,{'accepted':accepted,'skipped_length':skipped,'all_accepted_target_tokens':target_tokens,'selected_examples':len(chosen),'selected_target_tokens':sum(e['target_tokens'] for e in chosen),'sequence_percentiles':{str(p):float(np.percentile(lengths,p)) for p in (50,90,95,99)}}
