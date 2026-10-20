"""The bundled C DLL is platform-specific and independent of CPython's ABI."""
from setuptools import setup
from wheel.bdist_wheel import bdist_wheel


class NativeWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure=False

    def get_tag(self):
        return 'py3','none','win_amd64'


setup(cmdclass={'bdist_wheel':NativeWheel})
