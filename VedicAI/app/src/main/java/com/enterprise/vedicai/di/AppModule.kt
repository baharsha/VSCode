package com.enterprise.vedicai.di

import com.enterprise.vedicai.data.repository.AiRepositoryImpl
import com.enterprise.vedicai.data.repository.PanchangRepositoryImpl
import com.enterprise.vedicai.domain.repository.AiRepository
import com.enterprise.vedicai.domain.repository.PanchangRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class AppModule {

    @Binds
    @Singleton
    abstract fun bindPanchangRepository(
        panchangRepositoryImpl: PanchangRepositoryImpl
    ): PanchangRepository

    @Binds
    @Singleton
    abstract fun bindAiRepository(
        aiRepositoryImpl: AiRepositoryImpl
    ): AiRepository
}
