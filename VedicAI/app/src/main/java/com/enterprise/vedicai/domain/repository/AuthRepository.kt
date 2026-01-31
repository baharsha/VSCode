package com.enterprise.vedicai.domain.repository

import com.enterprise.vedicai.domain.model.User
import kotlinx.coroutines.flow.Flow

interface AuthRepository {
    val currentUser: Flow<User?>
    suspend fun signUp(name: String, email: String, password: String): Result<User>
    suspend fun login(email: String, password: String): Result<User>
    suspend fun logout()
    suspend fun updateProfile(user: User): Result<Unit>
}
