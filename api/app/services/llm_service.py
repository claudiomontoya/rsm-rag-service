from __future__ import annotations
from typing import List, Dict, Any
from app.config import OPENAI_API_KEY, LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from app.obs.decorators import traced
from app.obs.langfuse import trace_with_langfuse, log_llm_call
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

class LLMService:
    """LLM service for answer generation."""
    
    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.client = None
        
        if self.provider == "openai" and OPENAI_API_KEY:
            from openai import OpenAI
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info(f"LLM service initialized with OpenAI: {self.model}")
        else:
            logger.info("LLM service initialized with dummy provider")
    
    @traced("llm_generate_answer", langfuse_trace=True)
    async def generate_answer(self, question: str, sources: List[Dict[str, Any]]) -> str:
        """Generate answer using configured LLM."""
        
        if not sources:
            return "I couldn't find relevant information to answer your question."
        
        # Build context from sources
        context_parts = []
        for i, source in enumerate(sources[:5], 1):
            text = source["text"][:500]
            score = source.get("score", 0)
            context_parts.append(f"Source {i} (score: {score:.3f}): {text}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Based on the following sources, answer the question accurately and concisely.

SOURCES:
{context}

QUESTION: {question}

ANSWER: Provide a clear, accurate answer based only on the information in the sources above. If the sources don't contain enough information to answer the question, say so."""

        if self.provider == "openai" and self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                answer = response.choices[0].message.content
                
                # Log to Langfuse
                with trace_with_langfuse("llm_call") as lf_ctx:
                    if lf_ctx and lf_ctx.get("trace"):
                        log_llm_call(
                            lf_ctx["trace"],
                            model=self.model,
                            input_text=prompt,
                            output_text=answer,
                            usage={
                                "prompt_tokens": response.usage.prompt_tokens,
                                "completion_tokens": response.usage.completion_tokens,
                                "total_tokens": response.usage.total_tokens
                            }
                        )
                
                logger.info(f"LLM answer generated", 
                           model=self.model,
                           answer_length=len(answer),
                           total_tokens=response.usage.total_tokens)
                
                return answer
                
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                return f"Error generating answer with {self.model}: {str(e)}"
        else:
            # Dummy LLM for testing without API key
            logger.info("Using dummy LLM response")
            return f"[DUMMY LLM] Based on {len(sources)} sources, here's a summary: {sources[0]['text'][:200]}..."

llm_service = LLMService()