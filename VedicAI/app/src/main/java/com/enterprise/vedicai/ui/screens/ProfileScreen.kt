package com.enterprise.vedicai.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen() {
    var name by remember { mutableStateOf("") }
    var dob by remember { mutableStateOf("") }
    var tob by remember { mutableStateOf("") }
    var pob by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("My Birth Details", fontWeight = FontWeight.Bold) }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                "Provide your birth details for high-precision AI calculations and personalized daily forecasts.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Full Name") },
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) }
            )

            OutlinedTextField(
                value = dob,
                onValueChange = { dob = it },
                label = { Text("Date of Birth (DD/MM/YYYY)") },
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = { Icon(Icons.Default.CalendarToday, contentDescription = null) }
            )

            OutlinedTextField(
                value = tob,
                onValueChange = { tob = it },
                label = { Text("Time of Birth (HH:MM AM/PM)") },
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = { Icon(Icons.Default.AccessTime, contentDescription = null) }
            )

            OutlinedTextField(
                value = pob,
                onValueChange = { pob = it },
                label = { Text("Place of Birth") },
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = { Icon(Icons.Default.LocationOn, contentDescription = null) }
            )

            Button(
                onClick = { /* Save details */ },
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(16.dp)
            ) {
                Text("Save and Calculate My Chart")
            }

            Spacer(modifier = Modifier.height(24.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)
            ) {
                Row(modifier = Modifier.padding(16.dp)) {
                    Icon(Icons.Default.Security, contentDescription = null)
                    Spacer(Modifier.width(12.dp))
                    Text(
                        "Enterprise Security: Your birth data is encrypted using AES-256 and never shared with third parties.",
                        style = MaterialTheme.typography.labelSmall
                    )
                }
            }
        }
    }
}
