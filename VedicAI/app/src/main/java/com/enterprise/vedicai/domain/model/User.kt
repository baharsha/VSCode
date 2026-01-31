package com.enterprise.vedicai.domain.model

data class User(
    val id: String,
    val name: String,
    val email: String,
    val dateOfBirth: String? = null,
    val timeOfBirth: String? = null,
    val placeOfBirth: String? = null,
    val birthNakshatra: String? = null,
    val birthRashi: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val preferredLanguage: String = "English",
    val preferredAyanamsa: String = "Lahiri",
    val isGuest: Boolean = false
)
