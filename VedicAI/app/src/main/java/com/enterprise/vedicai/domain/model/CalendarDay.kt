package com.enterprise.vedicai.domain.model

import java.time.LocalDate

data class CalendarDay(
    val date: LocalDate,
    val tithiName: String,
    val isFestival: Boolean,
    val festivalName: String? = null,
    val isToday: Boolean = false,
    val isSelected: Boolean = false
)
