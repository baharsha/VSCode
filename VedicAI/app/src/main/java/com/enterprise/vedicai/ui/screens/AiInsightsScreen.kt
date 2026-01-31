package com.enterprise.vedicai.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel

@Composable
fun AiInsightsScreen(viewModel: VedicViewModel) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("AI Insights Screen")
    }
}
