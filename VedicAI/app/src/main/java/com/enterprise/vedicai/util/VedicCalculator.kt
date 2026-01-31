package com.enterprise.vedicai.util

import com.enterprise.vedicai.domain.model.*
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import kotlin.math.floor

object VedicCalculator {

    fun calculateDetailedPanchang(
        date: LocalDate,
        latitude: Double,
        longitude: Double,
        ayanamsa: String = "Lahiri"
    ): Panchang {
        // Mock data logic for specific date
        val sunriseTime = LocalTime.of(6, 12)
        val sunsetTime = LocalTime.of(18, 45)
        val sunriseStr = "06:12 AM"
        val sunsetStr = "06:45 PM"

        val tithiEnd = LocalDateTime.of(date, LocalTime.of(14, 30))
        val tithi = TithiInfo(
            name = getMockTithiForDate(date),
            endDateTime = tithiEnd,
            progressPercentage = 65
        )

        val nakshatraEnd = LocalDateTime.of(date, LocalTime.of(22, 15))
        val nakshatra = NakshatraInfo(
            name = "Rohini",
            pada = 2,
            endDateTime = nakshatraEnd
        )

        return Panchang(
            date = date,
            sunrise = sunriseStr,
            sunset = sunsetStr,
            moonrise = "03:45 PM",
            moonset = "04:12 AM",
            tithi = tithi,
            nakshatra = nakshatra,
            yoga = "Siddha",
            karana = "Vanija",
            weekday = date.dayOfWeek.name.lowercase().replaceFirstChar { it.uppercase() },
            ayanamsa = ayanamsa,
            rahuKaal = TimeRange("Rahu Kaal", "10:30 AM", "12:00 PM", false),
            gulikaKaal = TimeRange("Gulika Kaal", "07:30 AM", "09:00 AM", false),
            yamaganda = TimeRange("Yamaganda", "03:00 PM", "04:30 PM", false),
            abhijitMuhurat = TimeRange("Abhijit Muhurat", "11:45 AM", "12:35 PM", true),
            brahmaMuhurta = TimeRange("Brahma Muhurta", "04:30 AM", "05:18 AM", true),
            choghadiya = calculateChoghadiya(sunriseTime, sunsetTime),
            planetaryPositions = getMockPlanetaryPositions()
        )
    }

    fun getMonthCalendar(yearMonth: YearMonth): List<CalendarDay> {
        val daysInMonth = yearMonth.lengthOfMonth()
        return (1..daysInMonth).map { day ->
            val date = yearMonth.atDay(day)
            CalendarDay(
                date = date,
                tithiName = getMockTithiForDate(date).split(", ").last(),
                isFestival = day % 10 == 0,
                festivalName = if (day % 10 == 0) "Mock Festival" else null,
                isToday = date == LocalDate.now()
            )
        }
    }

    private fun getMockTithiForDate(date: LocalDate): String {
        val tithis = listOf("Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima", "Amavasya")
        val index = (date.dayOfMonth - 1) % tithis.size
        val paksha = if (date.dayOfMonth <= 15) "Shukla" else "Krishna"
        return "$paksha ${tithis[index]}"
    }

    private fun calculateChoghadiya(sunrise: LocalTime, sunset: LocalTime): List<ChoghadiyaInfo> {
        return listOf(
            ChoghadiyaInfo("Shubha", "06:12 AM", "07:46 AM", ChoghadiyaQuality.GOOD),
            ChoghadiyaInfo("Roga", "07:46 AM", "09:20 AM", ChoghadiyaQuality.BAD),
            ChoghadiyaInfo("Udveg", "09:20 AM", "10:54 AM", ChoghadiyaQuality.BAD),
            ChoghadiyaInfo("Chara", "10:54 AM", "12:28 PM", ChoghadiyaQuality.NEUTRAL),
            ChoghadiyaInfo("Labha", "12:28 PM", "02:02 PM", ChoghadiyaQuality.GOOD),
            ChoghadiyaInfo("Amrita", "02:02 PM", "03:36 PM", ChoghadiyaQuality.GOOD),
            ChoghadiyaInfo("Kaala", "03:36 PM", "05:10 PM", ChoghadiyaQuality.BAD),
            ChoghadiyaInfo("Shubha", "05:10 PM", "06:45 PM", ChoghadiyaQuality.GOOD)
        )
    }

    private fun getMockPlanetaryPositions() = listOf(
        PlanetaryPosition("Sun", 245.5, 0.0, 1.0, 9, "Dhanu"),
        PlanetaryPosition("Moon", 45.2, 2.1, 13.5, 2, "Vrishabha"),
        PlanetaryPosition("Jupiter", 12.5, -0.5, -0.05, 1, "Mesha")
    )
}
