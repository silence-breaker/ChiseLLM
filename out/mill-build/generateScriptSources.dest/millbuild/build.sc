package millbuild

import _root_.mill.runner.MillBuildRootModule

object MiscInfo_build {
  implicit lazy val millBuildRootModuleInfo: _root_.mill.runner.MillBuildRootModule.Info = _root_.mill.runner.MillBuildRootModule.Info(
    Vector("/home/silence_breaker/git/ChiseLLM/out/mill-launcher/0.11.6.jar").map(_root_.os.Path(_)),
    _root_.os.Path("/home/silence_breaker/git/ChiseLLM"),
    _root_.os.Path("/home/silence_breaker/git/ChiseLLM"),
    _root_.scala.Seq()
  )
  implicit lazy val millBaseModuleInfo: _root_.mill.main.RootModule.Info = _root_.mill.main.RootModule.Info(
    millBuildRootModuleInfo.projectRoot,
    _root_.mill.define.Discover[build]
  )
}
import MiscInfo_build.{millBuildRootModuleInfo, millBaseModuleInfo}
object build extends build
class build extends _root_.mill.main.RootModule {

//MILL_ORIGINAL_FILE_PATH=/home/silence_breaker/git/ChiseLLM/build.sc
//MILL_USER_CODE_START_MARKER
import mill._
import mill.scalalib._

/**
 * ChiseLLM 项目 - Mill 构建配置
 * 
 * 这个配置文件帮助 IDE (如 VS Code + Metals) 正确识别 Chisel 依赖
 */
object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 依赖
  override def ivyDeps = Agg(
    ivy"org.chipsalliance::chisel:6.0.0"
  )
  
  // Scala 编译选项
  override def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit",
    "-encoding", "utf-8"
  )
  
  // Chisel 编译器插件
  override def scalacPluginIvyDeps = Agg(
    ivy"org.chipsalliance:::chisel-plugin:6.0.0"
  )
}

}