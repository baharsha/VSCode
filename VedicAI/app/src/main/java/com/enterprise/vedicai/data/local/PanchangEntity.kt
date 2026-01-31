package com.enterprise.vedicai.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "panchang_cache")
data class PanchangEntity(
    @PrimaryKey val date: String,
    val sunrise: String,
    val sunset: String,
    val moonrise: String,
    val moonset: String,
    val tithiName: String,
    val tithiProgress: Int,
    val nakshatraName: String,
    val nakshatraPada: Int,
    val yoga: String,
    val karana: String,
    val weekday: String,
    val rahuKaalStart: String,
    val rahuKaalEnd: String,
    val gulikaKaalStart: String,
    val gulikaKaalEnd: String,
    val yamagandaStart: String,
    val yamagandaEnd: String,
    val abhijitStart: String,
    val abhijitEnd: String,
    val brahmaStart: String,
    val brahmaEnd: String
)
