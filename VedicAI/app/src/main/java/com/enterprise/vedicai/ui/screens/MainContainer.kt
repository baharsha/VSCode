package com.enterprise.vedicai.ui.screens

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.enterprise.vedicai.ui.navigation.NavGraph
import com.enterprise.vedicai.ui.navigation.Screen
import com.enterprise.vedicai.ui.viewmodel.VedicViewModel

@Composable
fun MainContainer(viewModel: VedicViewModel) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val items = listOf(
        Screen.Panchang to Icons.Default.CalendarMonth,
        Screen.Calendar to Icons.Default.DateRange,
        Screen.AiInsights to Icons.Default.Info,
        Screen.VedicBot to Icons.Default.QuestionAnswer,
        Screen.Profile to Icons.Default.Person
    )

    Scaffold(
        bottomBar = {
            NavigationBar {
                items.forEach { (screen, icon) ->
                    NavigationBarItem(
                        icon = { Icon(icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        Surface(modifier = Modifier.padding(innerPadding)) {
            NavGraph(navController = navController, viewModel = viewModel)
        }
    }
}
