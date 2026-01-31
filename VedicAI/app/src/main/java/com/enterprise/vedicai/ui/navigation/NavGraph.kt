package com.enterprise.vedicai.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.enterprise.vedicai.ui.screens.*
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel

@Composable
fun NavGraph(
    navController: NavHostController,
    viewModel: VedicViewModel
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Panchang.route
    ) {
        composable(Screen.Panchang.route) {
            PanchangScreen(viewModel)
        }
        composable(Screen.Calendar.route) {
            CalendarScreen(viewModel)
        }
        composable(Screen.AiInsights.route) {
            AiInsightsScreen(viewModel)
        }
        composable(Screen.VedicBot.route) {
            VedicBotScreen(viewModel)
        }
        composable(Screen.Profile.route) {
            ProfileScreen()
        }
        composable("login") {
            LoginScreen(onLoginSuccess = {
                navController.navigate(Screen.Panchang.route) {
                    popUpTo("login") { inclusive = true }
                }
            })
        }
    }
}
