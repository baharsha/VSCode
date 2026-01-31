package com.enterprise.vedicai.domain.repository

import com.enterprise.vedicai.domain.model.Panchang
import java.time.LocalDate

interface PanchangRepository {
    suspend fun getPanchangForDate(date: LocalDate, latitude: Double, longitude: Double): Panchang
}
