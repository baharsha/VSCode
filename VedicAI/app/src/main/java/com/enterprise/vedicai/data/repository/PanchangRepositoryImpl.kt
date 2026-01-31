package com.enterprise.vedicai.data.repository

import com.enterprise.vedicai.data.local.PanchangDao
import com.enterprise.vedicai.data.local.PanchangEntity
import com.enterprise.vedicai.domain.model.*
import com.enterprise.vedicai.domain.repository.PanchangRepository
import java.time.LocalDate
import java.time.LocalDateTime
import javax.inject.Inject

class PanchangRepositoryImpl @Inject constructor(
    private val panchangDao: PanchangDao
) : PanchangRepository {

    override suspend fun getPanchangForDate(date: LocalDate, latitude: Double, longitude: Double): Panchang {
        val dateStr = date.toString()
        val cached = panchangDao.getPanchangForDate(dateStr)
        
        if (cached != null) {
            return cached.toDomain()
        }

        // Mock detailed data matching the new domain structure
        val newPanchang = Panchang(
            date = date,
            sunrise = "06:12 AM",
            sunset = "06:45 PM",
            moonrise = "03:45 PM",
            moonset = "04:12 AM",
            tithi = TithiInfo("Shukla Ekadashi", null, 65),
            nakshatra = NakshatraInfo("Rohini", 2, null),
            yoga = "Siddha",
            karana = "Vanija",
            weekday = "Monday",
            rahuKaal = TimeRange("Rahu Kaal", "10:30 AM", "12:00 PM", false),
            gulikaKaal = TimeRange("Gulika Kaal", "07:30 AM", "09:00 AM", false),
            yamaganda = TimeRange("Yamaganda", "03:00 PM", "04:30 PM", false),
            abhijitMuhurat = TimeRange("Abhijit Muhurat", "11:45 AM", "12:35 PM", true),
            brahmaMuhurta = TimeRange("Brahma Muhurta", "04:30 AM", "05:18 AM", true),
            choghadiya = emptyList(),
            planetaryPositions = emptyList()
        )

        panchangDao.insertPanchang(newPanchang.toEntity())
        return newPanchang
    }

    private fun PanchangEntity.toDomain() = Panchang(
        date = LocalDate.parse(date),
        sunrise = sunrise,
        sunset = sunset,
        moonrise = moonrise,
        moonset = moonset,
        tithi = TithiInfo(tithiName, null, tithiProgress),
        nakshatra = NakshatraInfo(nakshatraName, nakshatraPada, null),
        yoga = yoga,
        karana = karana,
        weekday = weekday,
        rahuKaal = TimeRange("Rahu Kaal", rahuKaalStart, rahuKaalEnd, false),
        gulikaKaal = TimeRange("Gulika Kaal", gulikaKaalStart, gulikaKaalEnd, false),
        yamaganda = TimeRange("Yamaganda", yamagandaStart, yamagandaEnd, false),
        abhijitMuhurat = TimeRange("Abhijit Muhurat", abhijitStart, abhijitEnd, true),
        brahmaMuhurta = TimeRange("Brahma Muhurta", brahmaStart, brahmaEnd, true),
        choghadiya = emptyList(),
        planetaryPositions = emptyList()
    )

    private fun Panchang.toEntity() = PanchangEntity(
        date = date.toString(),
        sunrise = sunrise,
        sunset = sunset,
        moonrise = moonrise,
        moonset = moonset,
        tithiName = tithi.name,
        tithiProgress = tithi.progressPercentage,
        nakshatraName = nakshatra.name,
        nakshatraPada = nakshatra.pada,
        yoga = yoga,
        karana = karana,
        weekday = weekday,
        rahuKaalStart = rahuKaal.startTime,
        rahuKaalEnd = rahuKaal.endTime,
        gulikaKaalStart = gulikaKaal.startTime,
        gulikaKaalEnd = gulikaKaal.endTime,
        yamagandaStart = yamaganda.startTime,
        yamagandaEnd = yamaganda.endTime,
        abhijitStart = abhijitMuhurat.startTime,
        abhijitEnd = abhijitMuhurat.endTime,
        brahmaStart = brahmaMuhurta.startTime,
        brahmaEnd = brahmaMuhurta.endTime
    )
}
