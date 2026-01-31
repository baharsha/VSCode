package com.enterprise.vedicai.domain.model

data class PlanetaryPosition(
    val name: String,
    val longitude: Double,
    val latitude: Double,
    val speed: Double,
    val house: Int,
    val rashi: String
)
