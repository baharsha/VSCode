package com.enterprise.vedicai.data.repository

import com.enterprise.vedicai.BuildConfig
import com.enterprise.vedicai.domain.model.AiInsight
import com.enterprise.vedicai.domain.model.Panchang
import com.enterprise.vedicai.domain.repository.AiRepository
import com.google.ai.client.generativeai.GenerativeModel
import com.google.ai.client.generativeai.type.content
import javax.inject.Inject

class AiRepositoryImpl @Inject constructor() : AiRepository {

    private val generativeModel = GenerativeModel(
        modelName = "gemini-1.5-flash",
        apiKey = BuildConfig.GEMINI_KEY
    )

    override suspend fun getDailyInsights(panchang: Panchang): AiInsight {
        val prompt = """
            You are a Vedic Scholar. Based on the following Panchang data for ${panchang.date}, 
            provide a spiritual insight, a practical suggestion, and a short mantra or practice.
            Panchang Data:
            - Tithi: ${panchang.tithi.name} (${panchang.tithi.progressPercentage}% complete)
            - Nakshatra: ${panchang.nakshatra.name} (Pada: ${panchang.nakshatra.pada})
            - Yoga: ${panchang.yoga}
            - Karana: ${panchang.karana}
            - Weekday: ${panchang.weekday}
            - Sunrise: ${panchang.sunrise}, Sunset: ${panchang.sunset}
            
            Return the response in 3 clear sections: Spiritual Insight, Practical Action, and Daily Practice.
        """.trimIndent()

        return try {
            val response = generativeModel.generateContent(prompt)
            val text = response.text ?: "Stay mindful and perform your duties with devotion."
            AiInsight("Vedic Wisdom", text, "Hari Om Tat Sat")
        } catch (e: Exception) {
            AiInsight("Insight", "Stay positive today.", "Perform your duties with devotion.")
        }
    }

    override suspend fun askVedicQuestion(question: String, panchang: Panchang): String {
        val contextPrompt = content {
            text("You are a Vedic AI Scholar named 'Vedic Rishi'. You have access to the current Panchang data for ${panchang.date}:")
            text("- Tithi: ${panchang.tithi.name}")
            text("- Nakshatra: ${panchang.nakshatra.name}")
            text("- Yoga: ${panchang.yoga}")
            text("- Karana: ${panchang.karana}")
            text("- Weekday: ${panchang.weekday}")
            text("- Rahu Kaal: ${panchang.rahuKaal.startTime} to ${panchang.rahuKaal.endTime}")
            text("- Abhijit Muhurat: ${panchang.abhijitMuhurat.startTime} to ${panchang.abhijitMuhurat.endTime}")
            text("\nAnswer the user's question with wisdom, referring to the Panchang if relevant. Keep it concise but insightful.")
            text("\nUser Question: $question")
        }

        return try {
            val response = generativeModel.generateContent(contextPrompt)
            response.text ?: "I am reflecting on your question. Please ask again shortly."
        } catch (e: Exception) {
            "I'm sorry, I'm having trouble connecting to the cosmic energies right now. Please try again later. (Error: ${e.message})"
        }
    }
}
