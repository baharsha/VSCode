package com.enterprise.vedicai.domain.model

import java.time.LocalDate
import java.time.LocalDateTime

data class Panchang(
    val date: LocalDate,
    val sunrise: String,
    val sunset: String,
    val moonrise: String,
    val moonset: String,
    val tithi: TithiInfo,
    val nakshatra: NakshatraInfo,
    val yoga: String,
    val karana: String,
    val weekday: String,
    val ayanamsa: String = "Lahiri",
    val rahuKaal: TimeRange,
    val gulikaKaal: TimeRange,
    val yamaganda: TimeRange,
    val abhijitMuhurat: TimeRange,
    val brahmaMuhurta: TimeRange,
    val choghadiya: List<ChoghadiyaInfo>,
    val planetaryPositions: List<PlanetaryPosition>
)

data class TithiInfo(
    val name: String,
    val endDateTime: LocalDateTime?,
    val progressPercentage: Int
)

data class NakshatraInfo(
    val name: String,
    val pada: Int,
    val endDateTime: LocalDateTime?
)

data class TimeRange(
    val label: String,
    val startTime: String,
    val endTime: String,
    val isAuspicious: Boolean
)

data class ChoghadiyaInfo(
    val name: String,
    val startTime: String,
    val endTime: String,
    val quality: ChoghadiyaQuality
)

enum class ChoghadiyaQuality {
    GOOD, NEUTRAL, BAD
}
