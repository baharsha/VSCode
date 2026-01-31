package com.enterprise.vedicai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.enterprise.vedicai.domain.model.*
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PanchangScreen(viewModel: VedicViewModel) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            LargeTopAppBar(
                title = { 
                    Column {
                        Text("Vedic Panchang", fontWeight = FontWeight.Bold)
                        Text(
                            uiState.selectedDate.format(DateTimeFormatter.ofPattern("MMMM d, yyyy")),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { /* Open City Selector */ }) {
                        Icon(Icons.Default.LocationCity, contentDescription = "Select City")
                    }
                    IconButton(onClick = { /* Open Date Picker */ }) {
                        Icon(Icons.Default.DateRange, contentDescription = "Select Date")
                    }
                },
                colors = TopAppBarDefaults.largeTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = Color.White,
                    actionIconContentColor = Color.White
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            uiState.panchang?.let { panchang ->
                item { SunMoonCard(panchang) }
                
                item { SectionTitle("Core Panchanga") }
                item { CorePanchangaGrid(panchang) }

                item { SectionTitle("Choghadiya (Day)") }
                item { ChoghadiyaRow(panchang.choghadiya) }

                item { SectionTitle("Auspicious & Inauspicious Times") }
                item { MuhuratSection(panchang) }

                item { SectionTitle("Planetary Positions") }
                item { PlanetaryGrid(panchang.planetaryPositions) }
            }
        }
    }
}

@Composable
fun SunMoonCard(panchang: Panchang) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(16.dp)
    ) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            SunMoonItem(Icons.Default.WbSunny, "Sunrise", panchang.sunrise, "Sunset", panchang.sunset, Color(0xFFFF9800))
            VerticalDivider(modifier = Modifier.height(40.dp).align(Alignment.CenterVertically))
            SunMoonItem(Icons.Default.Nightlight, "Moonrise", panchang.moonrise, "Moonset", panchang.moonset, Color(0xFF3F51B5))
        }
    }
}

@Composable
fun SunMoonItem(icon: ImageVector, label1: String, time1: String, label2: String, time2: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(32.dp))
        Spacer(Modifier.width(8.dp))
        Column {
            Text("$label1: $time1", style = MaterialTheme.typography.labelSmall)
            Text("$label2: $time2", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun CorePanchangaGrid(panchang: Panchang) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        DetailItem("Tithi", panchang.tithi.name, "Ends at ${panchang.tithi.endDateTime?.format(DateTimeFormatter.ofPattern("HH:mm"))} (${panchang.tithi.progressPercentage}%)")
        DetailItem("Nakshatra", "${panchang.nakshatra.name} (Pada ${panchang.nakshatra.pada})", "Ends at ${panchang.nakshatra.endDateTime?.format(DateTimeFormatter.ofPattern("HH:mm"))}")
        DetailItem("Yoga", panchang.yoga, "")
        DetailItem("Karana", panchang.karana, "")
        DetailItem("Weekday", panchang.weekday, "")
    }
}

@Composable
fun DetailItem(label: String, value: String, subValue: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(label, style = MaterialTheme.typography.labelMedium, color = Color.Gray)
                Text(value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
            }
            if (subValue.isNotEmpty()) {
                Text(subValue, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@Composable
fun ChoghadiyaRow(list: List<ChoghadiyaInfo>) {
    LazyColumn(modifier = Modifier.height(120.dp).fillMaxWidth()) {
        items(list.size) { index ->
            val item = list[index]
            val color = when(item.quality) {
                ChoghadiyaQuality.GOOD -> Color(0xFFE8F5E9)
                ChoghadiyaQuality.NEUTRAL -> Color(0xFFFFF3E0)
                ChoghadiyaQuality.BAD -> Color(0xFFFFEBEE)
            }
            Card(
                modifier = Modifier.padding(vertical = 2.dp).fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = color)
            ) {
                Row(Modifier.padding(8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(item.name, fontWeight = FontWeight.Bold)
                    Text("${item.startTime} - ${item.endTime}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
fun MuhuratSection(panchang: Panchang) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TimeRangeItem(panchang.abhijitMuhurat)
        TimeRangeItem(panchang.brahmaMuhurta)
        TimeRangeItem(panchang.rahuKaal)
        TimeRangeItem(panchang.yamaganda)
        TimeRangeItem(panchang.gulikaKaal)
    }
}

@Composable
fun TimeRangeItem(range: TimeRange) {
    val color = if (range.isAuspicious) Color(0xFF2E7D32) else Color(0xFFC62828)
    val bgColor = if (range.isAuspicious) Color(0xFFE8F5E9) else Color(0xFFFFEBEE)
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = bgColor)
    ) {
        Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(range.label, fontWeight = FontWeight.SemiBold, color = color)
            Text("${range.startTime} - ${range.endTime}", fontWeight = FontWeight.Bold, color = color)
        }
    }
}

@Composable
fun PlanetaryGrid(positions: List<PlanetaryPosition>) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        positions.forEach { pos ->
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(pos.name, style = MaterialTheme.typography.bodySmall)
                Text("${pos.rashi} (${String.format("%.2f", pos.longitude)}°)", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
fun SectionTitle(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
    )
}
