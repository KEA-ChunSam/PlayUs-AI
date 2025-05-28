import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline,GenerationConfig
from config.config import settings

# 모델 로드 (FP16 최적화)
tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-4b-it", token=settings.hf_token)

model = AutoModelForCausalLM.from_pretrained(
    "google/gemma-3-4b-it",
    token=settings.hf_token,
    torch_dtype=torch.float32, 
    device_map="auto",
    low_cpu_mem_usage=True
)

def generate_simulation_result(prompt: str):
    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=2048,       
                do_sample=False,           # 안정성을 위해 샘플링 끄기
                num_beams=1,              # 빔서치 끄기
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1,
                temperature=0.8,
            )
        
        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if full_text.startswith(prompt):
            return full_text[len(prompt):].lstrip()
        else:
            return full_text
            
    except Exception as e:
        return f"야구 시뮬레이션 생성 중 오류가 발생했습니다: {str(e)}"

def detect_profanity(prompt: str):
    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                do_sample=False,
                temperature=0.1,  # 일관성을 위해 낮게 설정
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return full_text[len(prompt):].strip() if full_text.startswith(prompt) else full_text
            
    except Exception as e:
        return '{"isCurse": false, "words": []}'
            
    except Exception as e:
        return f'{{"isCurse": false, "words": [], "error": "{str(e)}"}}'


def generate_text(prompt: str, max_tokens: int = 1024) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.8,  # 안정적인 값
            top_p=0.9,
            min_length=5,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            eos_token_id=tokenizer.eos_token_id
        )
    
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    result_only = full_output[len(prompt):].strip()
    return result_only



model.generation_config = GenerationConfig(
    do_sample=True,
    temperature=0.5, 
    max_new_tokens=2048,
    repetition_penalty=1.1
)


text_gen_pipeline = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=250,  
    do_sample=True,
    temperature=0.7,     
    top_p=0.95,
    pad_token_id=tokenizer.eos_token_id
)
