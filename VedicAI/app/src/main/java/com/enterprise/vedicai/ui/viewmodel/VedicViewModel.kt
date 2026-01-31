package com.enterprise.vedicai.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.enterprise.vedicai.domain.model.*
import com.enterprise.vedicai.domain.repository.*
import com.enterprise.vedicai.util.LocationService
import com.enterprise.vedicai.util.VedicCalculator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import javax.inject.Inject

data class VedicUiState(
    val selectedDate: LocalDate = LocalDate.now(),
    val currentMonth: YearMonth = YearMonth.now(),
    val panchang: Panchang? = null,
    val aiInsight: AiInsight? = null,
    val isLoading: Boolean = false,
    val chatHistory: List<Pair<String, String>> = emptyList(),
    val isChatLoading: Boolean = false,
    val user: User? = null,
    val location: Pair<Double, Double> = 28.6139 to 77.2090, // Default Delhi
    val calendarDays: List<CalendarDay> = emptyList()
)

@HiltViewModel
class VedicViewModel @Inject constructor(
    private val panchangRepository: PanchangRepository,
    private val aiRepository: AiRepository,
    private val authRepository: AuthRepository,
    private val locationService: LocationService
) : ViewModel() {

    private val _uiState = MutableStateFlow(VedicUiState())
    val uiState: StateFlow<VedicUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            authRepository.currentUser.collect { user ->
                _uiState.update { it.copy(user = user) }
            }
        }
        refreshLocationAndLoad()
        loadCalendar(YearMonth.now())
    }

    fun refreshLocationAndLoad() {
        viewModelScope.launch {
            val location = locationService.getCurrentLocation()
            if (location != null) {
                _uiState.update { it.copy(location = location.latitude to location.longitude) }
            }
            loadPanchang(_uiState.value.selectedDate)
        }
    }

    fun loadPanchang(date: LocalDate) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, selectedDate = date) }
            val loc = _uiState.value.location
            val panchang = panchangRepository.getPanchangForDate(date, loc.first, loc.second)
            val insight = aiRepository.getDailyInsights(panchang)
            
            _uiState.update { it.copy(
                panchang = panchang,
                aiInsight = insight,
                isLoading = false
            ) }
        }
    }

    fun loadCalendar(yearMonth: YearMonth) {
        val days = VedicCalculator.getMonthCalendar(yearMonth)
        _uiState.update { it.copy(currentMonth = yearMonth, calendarDays = days) }
    }

    fun askAi(question: String) {
        val currentPanchang = _uiState.value.panchang ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isChatLoading = true) }
            val answer = aiRepository.askVedicQuestion(question, currentPanchang)
            _uiState.update { it.copy(
                chatHistory = it.chatHistory + (question to answer),
                isChatLoading = false
            ) }
        }
    }
}
