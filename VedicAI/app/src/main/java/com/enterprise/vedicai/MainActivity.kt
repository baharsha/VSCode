package com.enterprise.vedicai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.enterprise.vedicai.ui.screens.MainContainer
import com.enterprise.vedicai.ui.theme.VedicAITheme
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    
    private val viewModel: VedicViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VedicAITheme {
                MainContainer(viewModel)
            }
        }
    }
}
