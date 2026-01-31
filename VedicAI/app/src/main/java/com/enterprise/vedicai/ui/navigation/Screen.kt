package com.enterprise.vedicai.ui.navigation

sealed class Screen(val route: String, val title: String) {
    object Panchang : Screen("panchang", "Panchang")
    object Calendar : Screen("calendar", "Calendar")
    object AiInsights : Screen("ai_insights", "Insights")
    object VedicBot : Screen("vedic_bot", "AI Scholar")
    object Profile : Screen("profile", "Profile")
}
