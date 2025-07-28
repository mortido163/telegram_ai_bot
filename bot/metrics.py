import time
import logging
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class RequestMetrics:
    provider: str
    response_time: float
    success: bool
    error_type: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class MetricsCollector:
    def __init__(self):
        self.requests: list[RequestMetrics] = []
        self.cache_hits = 0
        self.cache_misses = 0
        
    def record_request(self, provider: str, response_time: float, success: bool, error_type: str = None):
        """Записывает метрики запроса"""
        metric = RequestMetrics(
            provider=provider,
            response_time=response_time,
            success=success,
            error_type=error_type
        )
        self.requests.append(metric)
        
        # Логируем медленные запросы
        if response_time > 10.0:
            logger.warning(f"Slow request: {provider} took {response_time:.2f}s")
    
    def record_cache_hit(self):
        """Записывает попадание в кэш"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Записывает промах кэша"""
        self.cache_misses += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        if not self.requests:
            return {}
            
        successful_requests = [r for r in self.requests if r.success]
        failed_requests = [r for r in self.requests if not r.success]
        
        stats = {
            "total_requests": len(self.requests),
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / len(self.requests) if self.requests else 0,
            "avg_response_time": sum(r.response_time for r in successful_requests) / len(successful_requests) if successful_requests else 0,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
        }
        
        # Статистика по провайдерам
        provider_stats = {}
        for provider in set(r.provider for r in self.requests):
            provider_requests = [r for r in self.requests if r.provider == provider]
            provider_successful = [r for r in provider_requests if r.success]
            
            provider_stats[provider] = {
                "total": len(provider_requests),
                "successful": len(provider_successful),
                "success_rate": len(provider_successful) / len(provider_requests) if provider_requests else 0,
                "avg_response_time": sum(r.response_time for r in provider_successful) / len(provider_successful) if provider_successful else 0
            }
        
        stats["providers"] = provider_stats
        return stats
    
    def log_stats(self):
        """Логирует текущую статистику"""
        stats = self.get_stats()
        if stats:
            logger.info(f"Metrics: {stats}")
    
    def reset(self):
        """Сбрасывает метрики"""
        self.requests.clear()
        self.cache_hits = 0
        self.cache_misses = 0

# Глобальный экземпляр
metrics = MetricsCollector() 