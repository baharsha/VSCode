package com.enterprise.vedicai.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.enterprise.vedicai.domain.model.CalendarDay
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel
import java.time.format.TextStyle
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalendarScreen(viewModel: VedicViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    val monthYearLabel = "${uiState.currentMonth.month.getDisplayName(TextStyle.FULL, Locale.getDefault())} ${uiState.currentMonth.year}"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Hindu Calendar", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = { viewModel.loadCalendar(uiState.currentMonth.minusMonths(1)) }) {
                        Icon(Icons.Default.ChevronLeft, contentDescription = "Previous Month")
                    }
                    Text(monthYearLabel, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    IconButton(onClick = { viewModel.loadCalendar(uiState.currentMonth.plusMonths(1)) }) {
                        Icon(Icons.Default.ChevronRight, contentDescription = "Next Month")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(8.dp)
        ) {
            // Day of week header
            Row(modifier = Modifier.fillMaxWidth()) {
                listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat").forEach { day ->
                    Text(
                        text = day,
                        modifier = Modifier.weight(1f),
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.Gray
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            LazyVerticalGrid(
                columns = GridCells.Fixed(7),
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                // Add empty spaces for the first day of the month
                val firstDayOfWeek = uiState.currentMonth.atDay(1).dayOfWeek.value % 7
                items(firstDayOfWeek) {
                    Spacer(Modifier.size(60.dp))
                }

                items(uiState.calendarDays) { day ->
                    CalendarDayItem(day) {
                        viewModel.loadPanchang(day.date)
                        // In a real app, navigate back to Panchang screen
                    }
                }
            }
        }
    }
}

@Composable
fun CalendarDayItem(day: CalendarDay, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .aspectRatio(0.8f)
            .clickable { onClick() },
        colors = CardDefaults.cardColors(
            containerColor = if (day.isToday) MaterialTheme.colorScheme.primaryContainer else Color.White
        ),
        border = if (day.isFestival) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = day.date.dayOfMonth.toString(),
                fontWeight = FontWeight.ExtraBold,
                fontSize = 16.sp
            )
            Text(
                text = day.tithiName,
                fontSize = 8.sp,
                lineHeight = 10.sp,
                textAlign = TextAlign.Center,
                color = if (day.isFestival) MaterialTheme.colorScheme.primary else Color.Gray
            )
            if (day.isFestival) {
                Box(
                    modifier = Modifier
                        .padding(top = 2.dp)
                        .size(4.dp)
                        .background(MaterialTheme.colorScheme.primary, CircleShape)
                )
            }
        }
    }
}
