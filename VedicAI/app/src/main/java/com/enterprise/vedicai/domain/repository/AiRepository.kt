package com.enterprise.vedicai.domain.repository

import com.enterprise.vedicai.domain.model.AiInsight
import com.enterprise.vedicai.domain.model.Panchang

interface AiRepository {
    suspend fun getDailyInsights(panchang: Panchang): AiInsight
    suspend fun askVedicQuestion(question: String, panchang: Panchang): String
}
