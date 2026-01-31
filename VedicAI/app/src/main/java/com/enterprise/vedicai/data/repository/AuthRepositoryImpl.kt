package com.enterprise.vedicai.data.repository

import com.enterprise.vedicai.domain.model.User
import com.enterprise.vedicai.domain.repository.AuthRepository
import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.tasks.await
import javax.inject.Inject

class AuthRepositoryImpl @Inject constructor(
    private val firebaseAuth: FirebaseAuth?
) : AuthRepository {

    private val _currentUser = MutableStateFlow<User?>(null)
    override val currentUser: Flow<User?> = _currentUser

    override suspend fun signUp(name: String, email: String, password: String): Result<User> {
        val auth = firebaseAuth ?: return Result.failure(Exception("Firebase not initialized. Add google-services.json"))
        return try {
            val result = auth.createUserWithEmailAndPassword(email, password).await()
            val firebaseUser = result.user ?: return Result.failure(Exception("Signup failed"))
            val user = User(
                id = firebaseUser.uid,
                name = name,
                email = email,
                isGuest = false
            )
            _currentUser.value = user
            Result.success(user)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun login(email: String, password: String): Result<User> {
        val auth = firebaseAuth ?: return Result.failure(Exception("Firebase not initialized. Add google-services.json"))
        return try {
            val result = auth.signInWithEmailAndPassword(email, password).await()
            val firebaseUser = result.user ?: return Result.failure(Exception("Login failed"))
            val user = User(
                id = firebaseUser.uid,
                name = firebaseUser.displayName ?: "User",
                email = email,
                isGuest = false
            )
            _currentUser.value = user
            Result.success(user)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun logout() {
        firebaseAuth?.signOut()
        _currentUser.value = null
    }

    override suspend fun updateProfile(user: User): Result<Unit> {
        _currentUser.value = user
        return Result.success(Unit)
    }
}
