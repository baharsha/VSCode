package com.enterprise.vedicai.di

import android.content.Context
import com.enterprise.vedicai.data.repository.AuthRepositoryImpl
import com.enterprise.vedicai.domain.repository.AuthRepository
import com.google.firebase.FirebaseApp
import com.google.firebase.auth.FirebaseAuth
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object FirebaseModule {

    @Provides
    @Singleton
    fun provideFirebaseAuth(@ApplicationContext context: Context): FirebaseAuth? {
        return try {
            if (FirebaseApp.getApps(context).isEmpty()) {
                FirebaseApp.initializeApp(context)
            }
            FirebaseAuth.getInstance()
        } catch (e: Exception) {
            null
        }
    }

    @Provides
    @Singleton
    fun provideAuthRepository(
        @ApplicationContext context: Context,
        firebaseAuth: FirebaseAuth?
    ): AuthRepository = AuthRepositoryImpl(firebaseAuth)
}
